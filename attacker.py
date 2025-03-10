import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import time

class NcatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ncat Listener")
        
        self.status_label = tk.Label(root, text="Status: Not Running", fg="red")
        self.status_label.pack(pady=10)
        
        self.start_button = tk.Button(root, text="Start Ncat", command=self.start_ncat)
        self.start_button.pack(pady=5)
        
        self.stop_button = tk.Button(root, text="Stop Ncat", command=self.stop_ncat, state=tk.DISABLED)
        self.stop_button.pack(pady=5)
        
        self.ncat_process = None
        self.monitor_thread = None
        self.running = False

    def start_ncat(self):
        if self.ncat_process is None:
            self.running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_label.config(text="Status: Running", fg="green")
            self.monitor_thread = threading.Thread(target=self.monitor_ncat)
            self.monitor_thread.start()

    def stop_ncat(self):
        if self.ncat_process is not None:
            self.running = False
            self.ncat_process.terminate()
            self.ncat_process = None
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_label.config(text="Status: Not Running", fg="red")

    def monitor_ncat(self):
        while self.running:
            try:
                self.ncat_process = subprocess.Popen(["ncat", "-lvp", "4444"])
                self.ncat_process.wait()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                self.stop_ncat()
                break

if __name__ == "__main__":
    root = tk.Tk()
    app = NcatGUI(root)
    root.mainloop()
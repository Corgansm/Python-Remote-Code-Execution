import customtkinter as ctk
import tkinter as tk  # Import tkinter and alias it as tk
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
import pyautogui
import struct
from tkinter import scrolledtext, filedialog, messagebox, simpledialog, ttk
from ScreenShareTab import ScreenShareTab
from datetime import datetime, timedelta
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, HTTPServer
import requests
import sys
from database import DatabaseManager

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
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("Server started on port 8000...")
    httpd.serve_forever()

CHUNK_SIZE = 1024 * 1

# Updated color scheme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")  # Changed from "blue" to "dark-blue"

# Define a custom color palette
COLORS = {
    "bg_primary": "#1a1a2e",  # Dark blue-black for main background
    "bg_secondary": "#16213e",  # Slightly lighter blue for secondary elements
    "accent_primary": "#4361ee",  # Vibrant blue for primary accent
    "accent_secondary": "#3f37c9",  # Deeper blue for secondary accent
    "accent_success": "#4cc9f0",  # Cyan blue for success indicators
    "accent_warning": "#f72585",  # Pink for warnings/important elements
    "accent_danger": "#ff0a54",  # Red for danger/critical actions
    "text_primary": "#e6e6e6",  # Light gray for primary text
    "text_secondary": "#b0b0b0",  # Darker gray for secondary text
    "text_accent": "#4cc9f0",  # Cyan blue for accent text
    "border": "#2a2a4a",  # Border color
    "selection": "#4361ee",  # Selection highlight color
}



class NcatGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Corgan's RCE Tool")  # Updated title
        self.geometry("1130x1010")
        self.minsize(400, 400)  # Set minimum window size for responsiveness

        # Configure icon if available
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except:
            pass  # Ignore if icon setting fails

        # Initialize database
        style = ttk.Style()
        self.geometry(f"+{400}+{20}")  # Set the window position to x=100, y=100
        style.theme_use('default')
        
        # Screen streaming server socket
        self.stream_server_socket = None
        self.stream_server_port = 5001  # Port for screen streaming

        # Apply custom colors to Treeview
        style.configure("Treeview", background=COLORS["bg_secondary"], foreground=COLORS["text_primary"],
                        fieldbackground=COLORS["bg_secondary"], font=('Segoe UI', 10))
        style.configure("Treeview.Heading", background=COLORS["bg_primary"], foreground=COLORS["text_accent"],
                        font=('Segoe UI', 10, 'bold'))
        style.map("Treeview", background=[("selected", COLORS["selection"])],
                  foreground=[("selected", COLORS["text_primary"])])

        # Add alternating row colors
        def fixed_map(option):
            # Fix for setting background color with ttkinter
            return [elm for elm in style.map("Treeview", query_opt=option) if elm[:2] != ("!disabled", "readonly")]

        style.map("Treeview", foreground=fixed_map("foreground"), background=fixed_map("background"))

        # Add padding to cells
        style.configure("Treeview", rowheight=30, padding=5)

        # Initialize database
        self.db = DatabaseManager()

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
            "theme_color": "blue",  # Updated default theme color
            "timeout": 30
        }

        # Store connection IDs for database reference
        self.connection_db_ids = {}

        # Screen streaming components
        self.screen_frame = None
        self.video_label = None
        self.streaming_active = False
        self.screen_socket = None

        # Configure grid layout with better responsiveness
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)

        # Header frame with improved styling
        self.header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=COLORS["bg_secondary"])
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.header_frame.grid_columnconfigure(5, weight=1)  # Make the last column expandable

        # Port entry with improved styling
        self.port_label = ctk.CTkLabel(self.header_frame, text="Port:", text_color=COLORS["text_accent"])
        self.port_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

        self.port_entry = ctk.CTkEntry(self.header_frame, placeholder_text="Port", width=120,
                                      border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.port_entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        self.port_entry.insert(0, "4444")

        # IP entry with improved styling
        self.ip_label = ctk.CTkLabel(self.header_frame, text="Interface:", text_color=COLORS["text_accent"])
        self.ip_label.grid(row=0, column=2, padx=(10, 5), pady=10, sticky="w")

        self.ip_entry = ctk.CTkEntry(self.header_frame, placeholder_text="Interface", width=150,
                                    border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.ip_entry.grid(row=0, column=3, padx=5, pady=10, sticky="w")
        self.ip_entry.insert(0, "0.0.0.0")

        # Buttons with improved styling
        self.start_btn = ctk.CTkButton(self.header_frame, text="Start Listener",
                                     command=self.start_main_listener,
                                     fg_color=COLORS["accent_primary"],
                                     hover_color=COLORS["accent_secondary"],
                                     text_color=COLORS["text_primary"])
        self.start_btn.grid(row=0, column=4, padx=10, pady=10, sticky="w")

        self.stop_btn = ctk.CTkButton(self.header_frame, text="Stop All",
                                    command=self.stop_all_listeners,
                                    fg_color=COLORS["accent_danger"],
                                    hover_color="#CC3D3D",
                                    text_color=COLORS["text_primary"],
                                    state="disabled")
        self.stop_btn.grid(row=0, column=5, padx=10, pady=10, sticky="w")

        # Add settings button
        self.settings_btn = ctk.CTkButton(self.header_frame, text="Settings",
                                       command=self.open_settings,
                                       fg_color=COLORS["bg_primary"],
                                       hover_color=COLORS["accent_secondary"],
                                       text_color=COLORS["text_primary"])
        self.settings_btn.grid(row=0, column=6, padx=10, pady=10, sticky="e")

        # Status indicator with improved styling
        self.status_frame = ctk.CTkFrame(self.header_frame, fg_color=COLORS["bg_secondary"])
        self.status_frame.grid(row=0, column=7, padx=10, pady=10, sticky="e")

        self.status_indicator = ctk.CTkLabel(self.status_frame, text="●", text_color="#ff0000", font=("Arial", 20))
        self.status_indicator.pack(side="left", padx=5)

        self.status_text = ctk.CTkLabel(self.status_frame, text="Offline", text_color=COLORS["text_secondary"])
        self.status_text.pack(side="left", padx=5)

        # Create tabbed interface with improved styling
        self.tabview = ctk.CTkTabview(self, fg_color=COLORS["bg_primary"])
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Add tabs with better naming
        self.tabview.add("Console")
        self.tabview.add("Connections")
        self.tabview.add("History")
        self.tabview.add("Screen Share")

        # Make tabs responsive
        for tab_name in ["Console", "Connections", "History", "Screen Share"]:
            self.tabview.tab(tab_name).grid_columnconfigure(0, weight=1)
            self.tabview.tab(tab_name).grid_rowconfigure(0, weight=1)

        # Console tab with improved styling
        self.console_frame = ctk.CTkFrame(self.tabview.tab("Console"), fg_color=COLORS["bg_secondary"])
        self.console_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(0, weight=1)

        # Console output with improved styling
        self.console_output = scrolledtext.ScrolledText(self.console_frame, bg=COLORS["bg_primary"],
                                                      fg=COLORS["text_primary"], insertbackground=COLORS["text_primary"],
                                                      font=("Consolas", 11), bd=0, relief="flat")
        self.console_output.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.console_output.config(state="disabled")

        # Connections tab with improved styling (match console)
        self.connections_frame = ctk.CTkFrame(self.tabview.tab("Connections"), fg_color=COLORS["bg_secondary"])  # Changed from bg_primary
        self.connections_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.connections_frame.grid_columnconfigure(0, weight=1)
        self.connections_frame.grid_rowconfigure(0, weight=1)

        # Connections treeview with improved styling
        self.tree_frame = ctk.CTkFrame(self.connections_frame, fg_color=COLORS["bg_primary"])
        self.tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)

        # Create treeview with improved styling
        self.tree = ttk.Treeview(self.tree_frame, columns=("id", "ip", "port", "status", "os", "user"),
                                show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Configure treeview columns with better spacing
        self.tree.heading("id", text="ID")
        self.tree.heading("ip", text="IP Address")
        self.tree.heading("port", text="Port")
        self.tree.heading("status", text="Status")
        self.tree.heading("os", text="OS")
        self.tree.heading("user", text="User")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("ip", width=150)
        self.tree.column("port", width=80, anchor="center")
        self.tree.column("status", width=100, anchor="center")
        self.tree.column("os", width=150)
        self.tree.column("user", width=150)

        # Add scrollbar with improved styling
        self.tree_scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree_scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=self.tree_scrollbar.set)

        # Add right-click menu for connections
        self.tree.bind("<Button-3>", self.show_connection_menu)

        # History tab with improved styling
        self.history_frame = ctk.CTkFrame(self.tabview.tab("History"), fg_color=COLORS["bg_secondary"])
        self.history_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.history_frame.grid_columnconfigure(0, weight=1)
        self.history_frame.grid_rowconfigure(0, weight=0)  # Search bar
        self.history_frame.grid_rowconfigure(1, weight=1)  # History list
        
        # Screen Share tab
        # Screen Share tab - Instantiate the new class
        self.screen_share_tab = ScreenShareTab(self.tabview.tab("Screen Share"), self, COLORS)
        self.screen_share_tab.pack(fill="both", expand=True) # Use pack or grid as needed for the tab content

        # Search bar with improved styling
        self.search_frame = ctk.CTkFrame(self.history_frame, fg_color=COLORS["bg_secondary"])
        self.search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.search_label = ctk.CTkLabel(self.search_frame, text="Search:", text_color=COLORS["text_accent"])
        self.search_label.pack(side="left", padx=5)

        self.search_entry = ctk.CTkEntry(self.search_frame, placeholder_text="Search commands...", width=300,
                                       border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.search_entry.pack(side="left", padx=5)

        self.search_btn = ctk.CTkButton(self.search_frame, text="Search",
                                      command=self.search_history,
                                      fg_color=COLORS["accent_primary"],
                                      hover_color=COLORS["accent_secondary"],
                                      text_color=COLORS["text_primary"])
        self.search_btn.pack(side="left", padx=5)

        # Filter options with improved styling
        self.filter_label = ctk.CTkLabel(self.search_frame, text="Filter:", text_color=COLORS["text_accent"])
        self.filter_label.pack(side="left", padx=(20, 5))

        self.filter_var = ctk.StringVar(value="all")

        self.filter_all = ctk.CTkRadioButton(self.search_frame, text="All", variable=self.filter_var, value="all",
                                          command=self.filter_history, text_color=COLORS["text_primary"])
        self.filter_all.pack(side="left", padx=5)

        self.filter_sent = ctk.CTkRadioButton(self.search_frame, text="Sent", variable=self.filter_var, value="sent",
                                           command=self.filter_history, text_color=COLORS["text_primary"])
        self.filter_sent.pack(side="left", padx=5)

        self.filter_received = ctk.CTkRadioButton(self.search_frame, text="Received", variable=self.filter_var,
                                               value="received",
                                               command=self.filter_history, text_color=COLORS["text_primary"])
        self.filter_received.pack(side="left", padx=5)

        # History treeview with improved styling
        self.history_tree_frame = ctk.CTkFrame(self.history_frame, fg_color=COLORS["bg_secondary"])
        self.history_tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.history_tree_frame.grid_columnconfigure(0, weight=1)
        self.history_tree_frame.grid_rowconfigure(0, weight=1)

        # Create history treeview with improved styling
        self.history_tree = ttk.Treeview(self.history_tree_frame,
                                columns=("timestamp", "connection", "direction", "command"),
                                show="headings")
        self.history_tree.grid(row=0, column=0, sticky="nsew")

        # Configure history treeview columns with better spacing
        self.history_tree.heading("timestamp", text="Timestamp")
        self.history_tree.heading("connection", text="Connection")
        self.history_tree.heading("direction", text="Direction")
        self.history_tree.heading("command", text="Command")

        self.history_tree.column("timestamp", width=150)
        self.history_tree.column("connection", width=150)
        self.history_tree.column("direction", width=100, anchor="center")
        self.history_tree.column("command", width=400)

            # Replace the standard scrollbar with a custom CTkScrollbar
        self.history_scrollbar = ctk.CTkScrollbar(
            self.history_tree_frame,
            orientation="vertical",
            command=self.history_tree.yview,
            fg_color=COLORS["bg_primary"],  # Background color
            button_color=COLORS["accent_primary"],  # Scrollbar color
            button_hover_color=COLORS["accent_secondary"]  # Scrollbar hover color
    )
        self.history_scrollbar.grid(row=0, column=1, sticky="ns")

            # Configure the treeview to use our custom scrollbar
        self.history_tree.configure(yscrollcommand=self.history_scrollbar.set)

        # Style the treeview to match the dark theme
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                    background=COLORS["bg_secondary"],
                    foreground=COLORS["text_primary"],
                    fieldbackground=COLORS["bg_secondary"],
                    borderwidth=0)
        style.configure("Treeview.Heading",
                    background=COLORS["bg_primary"],
                    foreground=COLORS["text_accent"],
                    relief="flat")
        style.map("Treeview",
              background=[('selected', COLORS["selection"])],
              foreground=[('selected', COLORS["text_primary"])])
    
        # Add right-click menu for history
        self.history_tree.bind("<Button-3>", self.show_history_menu)
        self.history_tree.bind("<Double-1>", self.reuse_command)

        # Command input with improved styling
        self.input_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"])
        self.input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.input_frame.grid_columnconfigure(0, weight=1)
        

        self.command_label = ctk.CTkLabel(self.input_frame, text="Command:", text_color=COLORS["text_accent"])
        self.command_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Create the command entry
        self.command_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Enter command...",
                                        border_color=COLORS["border"], text_color=COLORS["text_primary"])

        # Make the column containing the command entry expandable
        self.input_frame.grid_columnconfigure(0, weight=1)

        # Place the command entry in the grid with sticky="ew" to expand horizontally
        self.command_entry.grid(row=0, column=0, padx=(75, 75), pady=10, sticky="ew")

        # Add command history navigation
        self.command_history_index = -1
        self.command_entry.bind("<Up>", self.navigate_command_history_up)
        self.command_entry.bind("<Down>", self.navigate_command_history_down)

        self.send_btn = ctk.CTkButton(self.input_frame, text="Send",
                                    command=self.send_command,
                                    fg_color=COLORS["accent_primary"],
                                    hover_color=COLORS["accent_secondary"],
                                    text_color=COLORS["text_primary"])
        self.send_btn.grid(row=0, column=1, padx=0, pady=0)

        # Bind Enter key to send command
        self.command_entry.bind("<Return>", lambda event: self.send_command())

        # Connection selector with improved styling
        self.connection_label = ctk.CTkLabel(self.input_frame, text="Connection:", text_color=COLORS["text_accent"])
        self.connection_label.grid(row=0, column=3, padx=10, pady=10)

        self.connection_var = ctk.StringVar(value="All")
        self.connection_dropdown = ctk.CTkOptionMenu(
        self.input_frame, 
        variable=self.connection_var,
        values=["All"],
        command=self.on_connection_dropdown_change,
        fg_color=COLORS["bg_primary"],
        button_color=COLORS["accent_primary"],
        button_hover_color=COLORS["accent_secondary"],
        dropdown_fg_color=COLORS["bg_primary"],
        dropdown_hover_color=COLORS["bg_secondary"],
        text_color=COLORS["text_primary"])

        self.connection_dropdown.grid(row=0, column=4, padx=10, pady=10)

        # Status bar with improved styling
        self.status_bar = ctk.CTkFrame(self, height=25, corner_radius=0, fg_color=COLORS["bg_secondary"])
        self.status_bar.grid(row=3, column=0, sticky="ew")

        self.status_bar_label = ctk.CTkLabel(self.status_bar, text="Ready", text_color=COLORS["text_secondary"])
        self.status_bar_label.pack(side="left", padx=10)

        self.connection_count_label = ctk.CTkLabel(self.status_bar, text="Connections: 0",
                                                    text_color=COLORS["text_secondary"])
        self.connection_count_label.pack(side="right", padx=10)

        # Load command history from database
        self.load_command_history()

        # Start HTTP server for file uploads in a separate thread
        threading.Thread(target=start_server, daemon=True).start()

        self.print_window_size_loop()

    def on_connection_dropdown_change(self, choice):
        """Called when dropdown selection changes"""
        print(f"Dropdown changed to: {choice}")
        #self.screen_share_tab.add_ip(choice)  # Update the screen share tab with the selected connection
        #self.screen_share_tab.update_connection_list()  # Update the connection list in the screen share tab


    def print_window_size_loop(self):
        """Continuously print the window size"""
        width = self.winfo_width()
        height = self.winfo_height()
        position = [self.winfo_x(), self.winfo_y()]

        #print(f"Window size: {width}x{height}")
        #print(f"Window position {position[0]}  {position[1]}")
        # Schedule this method to run again after 1 second
        self.after(1000, self.print_window_size_loop)

    def navigate_command_history_up(self, event):
        """Navigate up through command history"""
        if not self.command_history:
            return

        connection = self.connection_var.get()
        if connection not in self.command_history:
            return

        history = self.command_history[connection]
        if not history:
            return

        if self.command_history_index == -1:
            self.command_history_index = len(history) - 1
        elif self.command_history_index > 0:
            self.command_history_index -= 1

        self.command_entry.delete(0, "end")
        self.command_entry.insert(0, history[self.command_history_index])

        # Move cursor to end
        self.command_entry.icursor("end")

        return "break"  # Prevent default behavior

    def navigate_command_history_down(self, event):
        """Navigate down through command history"""
        if not self.command_history:
            return

        connection = self.connection_var.get()
        if connection not in self.command_history:
            return

        history = self.command_history[connection]
        if not history:
            return

        if self.command_history_index == -1:
            return

        if self.command_history_index < len(history) - 1:
            self.command_history_index += 1
            self.command_entry.delete(0, "end")
            self.command_entry.insert(0, history[self.command_history_index])
        elif self.command_history_index == len(history) - 1:
            self.command_history_index = -1
            self.command_entry.delete(0, "end")

        # Move cursor to end
        self.command_entry.icursor("end")

        return "break"  # Prevent default behavior

    def load_command_history(self):
        """Load command history from database"""
        try:
            # Initialize with "All" connections
            self.command_history["All"] = []

            # Get command history from database
            messages = self.db.get_all_messages()

            for message in messages:
                message_id, connection_id, timestamp, direction, content, ip, port = message

                # Create connection identifier
                connection_str = f"{ip}:{port}"

                # Initialize if not exists
                if connection_str not in self.command_history:
                    self.command_history[connection_str] = []

                # Add to connection-specific history
                if direction == "sent" and content not in self.command_history[connection_str]:
                    self.command_history[connection_str].append(content)

                # Add to "All" history
                if direction == "sent" and content not in self.command_history["All"]:
                    self.command_history["All"].append(content)

            # Update history tab
            self.update_history_tab()

        except Exception as e:
            print(f"Error loading command history: {e}")

    def update_history_tab(self):
        """Update the history tab with messages from database"""
        try:
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            # Get messages from database
            messages = self.db.get_all_messages()

            # Apply filter if needed
            filter_type = self.filter_var.get()

            for message in messages:
                message_id, connection_id, timestamp, direction, content, ip, port = message

                # Skip if filtered
                if filter_type != "all" and direction != filter_type:
                    continue

                # Format connection string
                connection_str = f"{ip}:{port}"

                # Add to treeview
                self.history_tree.insert("", "end", values=(timestamp, connection_str, direction, content))

        except Exception as e:
            print(f"Error updating history tab: {e}")

    def filter_history(self):
        """Filter history based on selected filter"""
        self.update_history_tab()

    def search_history(self):
        """Search command history"""
        search_term = self.search_entry.get().strip().lower()
        if not search_term:
            self.update_history_tab()
            return

        try:
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            # Get messages from database
            messages = self.db.search_messages(search_term)

            # Apply filter if needed
            filter_type = self.filter_var.get()

            for message in messages:
                message_id, connection_id, timestamp, direction, content, ip, port = message

                # Skip if filtered
                if filter_type != "all" and direction != filter_type:
                    continue

                # Format connection string
                connection_str = f"{ip}:{port}"

                # Add to treeview
                self.history_tree.insert("", "end", values=(timestamp, connection_str, direction, content))

        except Exception as e:
            print(f"Error searching history: {e}")

    def show_history_menu(self, event):
        """Show context menu for history items"""
        # Get the item that was clicked on
        item = self.history_tree.identify_row(event.y)
        if not item:
            return

        # Select the item
        self.history_tree.selection_set(item)

        # Create context menu
        menu = tk.Menu(self, tearoff=0, bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])
        menu.add_command(label="Reuse Command", command=lambda: self.reuse_command(None))
        menu.add_command(label="Copy Command", command=self.copy_command)
        menu.add_separator()
        menu.add_command(label="Delete Entry", command=self.delete_history_entry)

        # Display menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def reuse_command(self, event):
        """Reuse a command from history"""
        # Get selected item
        selection = self.history_tree.selection()
        if not selection:
            return

        # Get command from selected item
        item = selection[0]
        command = self.history_tree.item(item, "values")[3]

        # Set command in entry
        self.command_entry.delete(0, "end")
        self.command_entry.insert(0, command)

    def copy_command(self):
        """Copy a command to clipboard"""
        # Get selected item
        selection = self.history_tree.selection()
        if not selection:
            return

        # Get command from selected item
        item = selection[0]
        command = self.history_tree.item(item, "values")[3]

        # Copy to clipboard
        self.clipboard_clear()
        self.clipboard_append(command)

        # Update status
        self.update_status("Command copied to clipboard")

    def delete_history_entry(self):
        """Delete a history entry"""
        # Get selected item
        selection = self.history_tree.selection()
        if not selection:
            return

        # Get message ID from selected item
        item = selection[0]
        timestamp = self.history_tree.item(item, "values")[0]
        connection = self.history_tree.item(item, "values")[1]
        direction = self.history_tree.item(item, "values")[2]
        content = self.history_tree.item(item, "values")[3]

        # Delete from database
        try:
            self.db.delete_message(timestamp, connection, direction, content)

            # Update history tab
            self.update_history_tab()

            # Update status
            self.update_status("History entry deleted")

        except Exception as e:
            self.update_status("History entry deleted")
            
        except Exception as e:
            print(f"Error deleting history entry: {e}")
            messagebox.showerror("Error", f"Failed to delete history entry: {e}")

    def open_settings(self):
        """Open settings dialog"""
        # Create settings dialog
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("1280x720")
        settings_window.minsize(1280, 720)
        settings_window.grab_set()  # Make modal
        
        # Configure grid
        settings_window.grid_columnconfigure(0, weight=1)
        settings_window.grid_rowconfigure(0, weight=1)
        settings_window.grid_rowconfigure(1, weight=0)
        
        # Create tabview
        tabview = ctk.CTkTabview(settings_window, fg_color=COLORS["bg_primary"])
        tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Add tabs
        tabview.add("General")
        tabview.add("Appearance")
        tabview.add("Advanced")
        
        # General tab
        general_frame = ctk.CTkFrame(tabview.tab("General"), fg_color=COLORS["bg_secondary"])
        general_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Auto commands
        auto_commands_var = ctk.BooleanVar(value=self.settings["auto_commands"])
        auto_commands_cb = ctk.CTkCheckBox(general_frame, text="Auto-execute commands on connection",
                                         variable=auto_commands_var, text_color=COLORS["text_primary"],
                                         fg_color=COLORS["accent_primary"],
                                         hover_color=COLORS["accent_secondary"])
        auto_commands_cb.pack(anchor="w", padx=20, pady=10)
        
        # Notifications
        notifications_var = ctk.BooleanVar(value=self.settings["notifications"])
        notifications_cb = ctk.CTkCheckBox(general_frame, text="Show notifications",
                                        variable=notifications_var, text_color=COLORS["text_primary"],
                                        fg_color=COLORS["accent_primary"],
                                        hover_color=COLORS["accent_secondary"])
        notifications_cb.pack(anchor="w", padx=20, pady=10)
        
        # Command confirmation
        command_confirmation_var = ctk.BooleanVar(value=self.settings["command_confirmation"])
        command_confirmation_cb = ctk.CTkCheckBox(general_frame, text="Confirm potentially dangerous commands",
                                               variable=command_confirmation_var, text_color=COLORS["text_primary"],
                                               fg_color=COLORS["accent_primary"],
                                               hover_color=COLORS["accent_secondary"])
        command_confirmation_cb.pack(anchor="w", padx=20, pady=10)
        
        # Auto save logs
        auto_save_logs_var = ctk.BooleanVar(value=self.settings["auto_save_logs"])
        auto_save_logs_cb = ctk.CTkCheckBox(general_frame, text="Automatically save logs",
                                         variable=auto_save_logs_var, text_color=COLORS["text_primary"],
                                         fg_color=COLORS["accent_primary"],
                                         hover_color=COLORS["accent_secondary"])
        auto_save_logs_cb.pack(anchor="w", padx=20, pady=10)
        
        # Timeout
        timeout_frame = ctk.CTkFrame(general_frame, fg_color=COLORS["bg_secondary"])
        timeout_frame.pack(fill="x", padx=20, pady=10)
        
        timeout_label = ctk.CTkLabel(timeout_frame, text="Connection timeout (seconds):", text_color=COLORS["text_primary"])
        timeout_label.pack(side="left", padx=5)
        
        timeout_var = ctk.StringVar(value=str(self.settings["timeout"]))
        timeout_entry = ctk.CTkEntry(timeout_frame, textvariable=timeout_var, width=80,
                                  border_color=COLORS["border"], text_color=COLORS["text_primary"])
        timeout_entry.pack(side="left", padx=5)
        
        # Advanced tab
        advanced_frame = ctk.CTkFrame(tabview.tab("Advanced"), fg_color=COLORS["bg_secondary"])
        advanced_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Database path
        db_frame = ctk.CTkFrame(advanced_frame, fg_color=COLORS["bg_secondary"])
        db_frame.pack(fill="x", padx=20, pady=10)
        
        db_label = ctk.CTkLabel(db_frame, text="Database path:", text_color=COLORS["text_primary"])
        db_label.pack(side="left", padx=5)
        
        db_path_var = ctk.StringVar(value=self.db.db_path)
        db_entry = ctk.CTkEntry(db_frame, textvariable=db_path_var, width=300,
                             border_color=COLORS["border"], text_color=COLORS["text_primary"])
        db_entry.pack(side="left", padx=5)
        
        def browse_db():
            path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("Database files", "*.db")])
            if path:
                db_path_var.set(path)
                
        db_browse_btn = ctk.CTkButton(db_frame, text="Browse",
                                    command=browse_db, 
                                    fg_color=COLORS["accent_primary"], 
                                    hover_color=COLORS["accent_secondary"],
                                    text_color=COLORS["text_primary"])
        db_browse_btn.pack(side="left", padx=5)
        
        # Backup database
        backup_btn = ctk.CTkButton(advanced_frame, text="Backup Database",
                                 command=lambda: self.backup_database(db_path_var.get()), 
                                 fg_color=COLORS["accent_primary"], 
                                 hover_color=COLORS["accent_secondary"],
                                 text_color=COLORS["text_primary"])
        backup_btn.pack(anchor="w", padx=20, pady=10)
        
        # Clear database
        clear_btn = ctk.CTkButton(advanced_frame, text="Clear Database",
                                command=self.clear_database, 
                                fg_color=COLORS["accent_danger"], 
                                hover_color="#CC3D3D",
                                text_color=COLORS["text_primary"])
        clear_btn.pack(anchor="w", padx=20, pady=10)
        
        # Button frame
        button_frame = ctk.CTkFrame(settings_window, fg_color=COLORS["bg_secondary"])
        button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        # Save button
        save_btn = ctk.CTkButton(button_frame, text="Save",
                               command=lambda: self.save_settings(settings_window, {
                                   "auto_commands": auto_commands_var.get(),
                                   "notifications": notifications_var.get(),
                                   "command_confirmation": command_confirmation_var.get(),
                                   "auto_save_logs": auto_save_logs_var.get(),
                                   "theme_color": "dark-blue",
                                   "timeout": int(timeout_var.get())
                               }, db_path_var.get()), 
                               fg_color=COLORS["accent_primary"], 
                               hover_color=COLORS["accent_secondary"],
                               text_color=COLORS["text_primary"])
        save_btn.pack(side="right", padx=10)
        
        # Cancel button
        cancel_btn = ctk.CTkButton(button_frame, text="Cancel",
                                 command=settings_window.destroy, 
                                 fg_color=COLORS["bg_primary"], 
                                 hover_color=COLORS["accent_secondary"],
                                 text_color=COLORS["text_primary"])
        cancel_btn.pack(side="right", padx=10)

    def backup_database(self, db_path):
        """Backup the database"""
        try:
            # Get backup path
            backup_path = filedialog.asksaveasfilename(defaultextension=".db", 
                                                     filetypes=[("Database files", "*.db")],
                                                     initialfile="backup.db")
            if not backup_path:
                return
                
            # Backup database
            shutil.copy2(db_path, backup_path)
            
            # Show success message
            messagebox.showinfo("Backup", f"Database backed up to {backup_path}")
            
        except Exception as e:
            print(f"Error backing up database: {e}")
            messagebox.showerror("Error", f"Failed to backup database: {e}")

    def clear_database(self):
        """Clear the database"""
        if messagebox.askyesno("Clear Database", "Are you sure you want to clear the database? This will delete all connections, messages, and settings."):
            try:
                # Clear database
                self.db.clear_database()
                
                # Show success message
                messagebox.showinfo("Clear Database", "Database cleared successfully")
                
                # Update UI
                self.update_history_tab()
                
            except Exception as e:
                print(f"Error clearing database: {e}")
                messagebox.showerror("Error", f"Failed to clear database: {e}")

    def save_settings(self, window, settings, db_path):
        """Save settings"""
        try:
            # Update settings
            self.settings.update(settings)
            
            # Save settings to database
            for key, value in self.settings.items():
                self.db.set_setting(key, value)
                
            # Check if database path changed
            if db_path != self.db.db_path:
                # Ask for confirmation
                if messagebox.askyesno("Database Path", "Changing the database path requires restarting the application. Continue?"):
                    # Save new path to a config file
                    with open("config.json", "w") as f:
                        json.dump({"db_path": db_path}, f)
                        
                    # Restart application
                    self.restart_application()
                    
            # Close window
            window.destroy()
            
            # Update UI
            self.apply_settings()
            
        except Exception as e:
            print(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def apply_settings(self):
        """Apply settings to UI"""
        try:
            # Apply theme
            ctk.set_default_color_theme(self.settings["theme_color"])
            
            # Update status
            self.update_status("Settings applied")
            
        except Exception as e:
            print(f"Error applying settings: {e}")

    def restart_application(self):
        """Restart the application"""
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def update_status(self, message):
        """Update status bar message"""
        self.status_bar_label.configure(text=message)
        
        # Schedule reset after 5 seconds
        self.after(5000, lambda: self.status_bar_label.configure(text="Ready"))

    def start_main_listener(self):
        """Start the main listener"""
        try:
            port = int(self.port_entry.get())
            ip = self.ip_entry.get()
            
            # Validate port
            if port < 1 or port > 65535:
                messagebox.showerror("Error", "Port must be between 1 and 65535")
                return
                
            # Check if listener already exists
            if port in self.listeners:
                messagebox.showerror("Error", f"Listener already running on port {port}")
                return
                
            # Create socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                server_socket.bind((ip, port))
                server_socket.listen(5)
                
                # Store listener
                self.listeners[port] = server_socket
                self.main_listener = server_socket
                
                # Update UI
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
                self.status_indicator.configure(text="●", text_color="#00ff00")
                self.status_text.configure(text="Online")
                
                # Update console
                self.update_console(f"[+] Listener started on {ip}:{port}", "success")
                
                # Start listener thread
                threading.Thread(target=self.accept_connections, args=(server_socket, port), daemon=True).start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start listener: {e}")
                server_socket.close()
                
        except ValueError:
            messagebox.showerror("Error", "Port must be a number")

    def accept_connections(self, server_socket, port):
        """Accept incoming connections"""
        try:
            while True:
                try:
                    client_socket, address = server_socket.accept()
                    
                    # Set timeout
                    client_socket.settimeout(self.settings["timeout"])
                    
                    # Update console
                    self.update_console(f"[+] Connection received from {address[0]}:{address[1]}", "success")
                    
                    # Start client handler thread
                    threading.Thread(target=self.handle_client, args=(client_socket, address), daemon=True).start()
                    
                except socket.timeout:
                    continue
                    
                except Exception as e:
                    if server_socket in self.listeners.values():
                        self.update_console(f"[-] Error accepting connection: {e}", "error")
                    else:
                        # Listener was stopped
                        break
                        
        except Exception as e:
            self.update_console(f"[-] Listener error: {e}", "error")

    def handle_client(self, client_socket, address):
        """Handle client connection"""
        try:
            # Get client info
            client_info = {}
            client_info["ip"] = address[0]
            client_info["port"] = address[1]
            
            # Add to active connections
            self.connection_count += 1
            connection_id = self.connection_count
            self.active_connections.append(connection_id)
            self.connection_sockets[connection_id] = client_socket
            
            # Add to connection info
            self.connection_info[connection_id] = client_info
            
            # Initialize command history
            connection_str = f"{address[0]}:{address[1]}"
            if connection_str not in self.command_history:
                self.command_history[connection_str] = []
                
            # Update connection dropdown
            self.update_connection_dropdown()
            
            # Update connection count
            self.connection_count_label.configure(text=f"Connections: {len(self.active_connections)}")
            
            # Add to treeview
            self.tree.insert("", "end", iid=str(connection_id), values=(connection_id, address[0], address[1], "Connected", "Unknown", "Unknown"))
            
            # Log connection to database
            db_id = self.db.log_connection(address[0], address[1])
            self.connection_db_ids[connection_id] = db_id
                
            # Handle commands
            while True:
                try:

                    # Receive data
                    data = client_socket.recv(4096)
                    if not data:
                        break
                        
                    # Decode data
                    message = data.decode()
                    
                    # Check for special messages
                    if message.startswith("SCREEN_SIZE:"):
                        # Parse screen size
                        size_info = message.split(":", 1)[1].strip()
                        width, height = map(int, size_info.split("x"))
                        
                        # Store screen size
                        client_info["screen_width"] = width
                        client_info["screen_height"] = height
                        self.client_width = width
                        self.client_height = height
                        
                        # Calculate scaling factors
                        self.stream_scale_x = min(1.0, 800 / width)
                        self.stream_scale_y = min(1.0, 600 / height)
                        
                        continue
                        
                    # Check for whoami command response
                    elif "OS:" in message and "Username:" in message:
                        lines = message.strip().split('\n')
                        for line in lines:
                            if line.startswith("OS:"):
                                os_info = line.split(":", 1)[1].strip()
                                self.connection_info[connection_id]["os"] = os_info
                            elif line.startswith("Username:"):
                                user_info = line.split(":", 1)[1].strip()
                                self.connection_info[connection_id]["user"] = user_info
                            
                        # Update treeview with new information
                        self.screen_share_tab.add_ip(connection_id)
                        self.tree.item(str(connection_id), values=(
                            connection_id,
                            self.connection_info[connection_id]["ip"],
                            self.connection_info[connection_id]["port"],
                            "Connected",
                            self.connection_info[connection_id].get("os", "Unknown"),
                            self.connection_info[connection_id].get("user", "Unknown")
                        ))
                            
                        # Log the update
                        self.update_console(f"[+] Updated user and OS information for connection {connection_id}", "success")
                        
                        
                    # Log message to database
                    self.db.log_message(db_id, message, "received")
                    
                    # Update console
                    self.update_console(f"[{connection_id}] {message}")
                    
                except socket.timeout:
                    # Check if connection is still active
                    try:
                        self.connection_sockets[connection_id].send(f"".encode())
                    except:
                        break
                        
                except Exception as e:
                    self.update_console(f"[-] Error receiving data: {e}", "error")
                    break
                    
            # Connection closed
            self.handle_disconnection(connection_id)
            
        except Exception as e:
            self.update_console(f"[-] Error handling client: {e}", "error")
            
            # Connection closed
            if connection_id in self.active_connections:
                self.handle_disconnection(connection_id)

    def handle_disconnection(self, connection_id):
        """Handle client disconnection"""
        try:
            # Remove from active connections
            if connection_id in self.active_connections:
                self.active_connections.remove(connection_id)
                
            # Close socket
            if connection_id in self.connection_sockets:
                try:
                    self.connection_sockets[connection_id].close()
                except:
                    pass
                del self.connection_sockets[connection_id]
                
            # Update treeview
            try:
                self.tree.item(str(connection_id), values=(connection_id, 
                                                        self.connection_info[connection_id]["ip"], 
                                                        self.connection_info[connection_id]["port"], 
                                                        "Disconnected", 
                                                        self.connection_info[connection_id].get("os", "Unknown"), 
                                                        self.connection_info[connection_id].get("user", "Unknown")))
            except:
                pass
                
            # Update connection dropdown
            self.update_connection_dropdown()
            
            # Update connection count
            self.connection_count_label.configure(text=f"Connections: {len(self.active_connections)}")
            
            # Update console
            self.update_console(f"[-] Connection {connection_id} closed", "warning")
            
            # Update database
            if connection_id in self.connection_db_ids:
                self.db.update_disconnect_time(self.connection_db_ids[connection_id])
                
        except Exception as e:
            self.update_console(f"[-] Error handling disconnection: {e}", "error")

    def update_connection_dropdown(self):
        """Update connection dropdown"""
        try:
            # Get current selection
            current = self.connection_var.get()
            
            # Create list of connections
            connections = ["All"]
            for conn_id in self.active_connections:
                if conn_id in self.connection_info:
                    ip = self.connection_info[conn_id]["ip"]
                    port = self.connection_info[conn_id]["port"]
                    connections.append(f"{ip}:{port}")
                    self.screen_share_tab.add_ip(conn_id)
                    
            # Update dropdown
            self.connection_dropdown.configure(values=connections)
            
            # Restore selection if possible
            if current in connections:
                self.connection_var.set(current)
            else:
                self.connection_var.set("All")

            print(connections)
                
        except Exception as e:
            print(f"Error updating connection dropdown: {e}")

    def send_specific_command(self, command):
        # Get selected connection
        connection = self.connection_var.get()

        # Add to command history
        if connection not in self.command_history:
            self.command_history[connection] = []
            
        if command not in self.command_history[connection]:
            self.command_history[connection].append(command)
            
        # Reset command history index
        self.command_history_index = -1
        
        # Clear command entry
        self.command_entry.delete(0, "end")
        
        # Send to all connections
        if connection == "All":
            for conn_id in self.active_connections:
                try:
                    # Send command
                    self.connection_sockets[conn_id].send(command.encode())
                    
                    # Update console
                    self.update_console(f"[{conn_id}] > {command}", "command")
                    
                    # Log command to database
                    if conn_id in self.connection_db_ids:
                        self.db.log_message(self.connection_db_ids[conn_id], command, "sent")
                        
                except Exception as e:
                    self.update_console(f"[-] Error sending command to connection {conn_id}: {e}", "error")
                    
        # Send to specific connection
        else:
            # Find connection ID
            conn_id = None
            for cid in self.active_connections:
                if cid in self.connection_info:
                    ip = self.connection_info[cid]["ip"]
                    port = self.connection_info[cid]["port"]
                    if f"{ip}:{port}" == connection:
                        conn_id = cid
                        break
                        
            if conn_id is None:
                messagebox.showerror("Error", f"Connection {connection} not found")
                return
                
            try:
                # Send command
                self.connection_sockets[conn_id].send(command.encode())
                
                # Update console
                self.update_console(f"[{conn_id}] > {command}", "command")
                
                # Log command to database
                if conn_id in self.connection_db_ids:
                    self.db.log_message(self.connection_db_ids[conn_id], command, "sent")
                    
            except Exception as e:
                self.update_console(f"[-] Error sending command to connection {conn_id}: {e}", "error")
                
        # Update history tab
        self.update_history_tab()

    def send_command(self):
        """Send command to selected connection"""
        command = self.command_entry.get().strip()
        if not command:
            return
            
        # Check if any connections are active
        if not self.active_connections:
            messagebox.showerror("Error", "No active connections")
            return

        # Get selected connection
        connection = self.connection_var.get()
        
        # Check if any connections are active
        if not self.active_connections:
            messagebox.showerror("Error", "No active connections")
            return
            
        # Check for dangerous commands
        dangerous_commands = ["rm", "del", "format", "shutdown", "reboot"]
        is_dangerous = any(command.lower().startswith(cmd) for cmd in dangerous_commands)
        
        if is_dangerous and self.settings["command_confirmation"]:
            if not messagebox.askyesno("Confirm", f"The command '{command}' may be dangerous. Continue?"):
                return
                
        # Add to command history
        if connection not in self.command_history:
            self.command_history[connection] = []
            
        if command not in self.command_history[connection]:
            self.command_history[connection].append(command)
            
        # Reset command history index
        self.command_history_index = -1
        
        # Clear command entry
        self.command_entry.delete(0, "end")
        
        # Send to all connections
        if connection == "All":
            for conn_id in self.active_connections:
                try:
                    # Send command
                    self.connection_sockets[conn_id].send(command.encode())
                    
                    # Update console
                    self.update_console(f"[{conn_id}] > {command}", "command")
                    
                    # Log command to database
                    if conn_id in self.connection_db_ids:
                        self.db.log_message(self.connection_db_ids[conn_id], command, "sent")
                        
                except Exception as e:
                    self.update_console(f"[-] Error sending command to connection {conn_id}: {e}", "error")
                    
        # Send to specific connection
        else:
            # Find connection ID
            conn_id = None
            for cid in self.active_connections:
                if cid in self.connection_info:
                    ip = self.connection_info[cid]["ip"]
                    port = self.connection_info[cid]["port"]
                    if f"{ip}:{port}" == connection:
                        conn_id = cid
                        break
                        
            if conn_id is None:
                messagebox.showerror("Error", f"Connection {connection} not found")
                return
                
            try:
                # Send command
                self.connection_sockets[conn_id].send(command.encode())
                
                # Update console
                self.update_console(f"[{conn_id}] > {command}", "command")
                
                # Log command to database
                if conn_id in self.connection_db_ids:
                    self.db.log_message(self.connection_db_ids[conn_id], command, "sent")
                    
            except Exception as e:
                self.update_console(f"[-] Error sending command to connection {conn_id}: {e}", "error")
                
        # Update history tab
        self.update_history_tab()

    def update_console(self, message, message_type="normal"):
        """Update console with message"""
        self.console_output.config(state="normal")
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console_output.insert("end", f"[{timestamp}] ", "timestamp")
        
        # Add message with appropriate tag
        if message_type == "success":
            self.console_output.insert("end", f"{message}\n", "success")
        elif message_type == "error":
            self.console_output.insert("end", f"{message}\n", "error")
        elif message_type == "warning":
            self.console_output.insert("end", f"{message}\n", "warning")
        elif message_type == "info":
            self.console_output.insert("end", f"{message}\n", "info")
        elif message_type == "command":
            self.console_output.insert("end", f"{message}\n", "command")
        else:
            self.console_output.insert("end", f"{message}\n")
            
        # Configure tags
        self.console_output.tag_configure("timestamp", foreground=COLORS["text_secondary"])
        self.console_output.tag_configure("success", foreground=COLORS["accent_success"])
        self.console_output.tag_configure("error", foreground=COLORS["accent_danger"])
        self.console_output.tag_configure("warning", foreground=COLORS["accent_warning"])
        self.console_output.tag_configure("info", foreground=COLORS["text_accent"])
        self.console_output.tag_configure("command", foreground=COLORS["accent_primary"])
        
        # Scroll to end
        self.console_output.see("end")
        self.console_output.config(state="disabled")

    # add_ip from screensharetab
    

    def show_connection_menu(self, event):
        """Show a custom context menu using CTkFrame and CTkButton"""
        # Get the item that was clicked on
        item = self.tree.identify_row(event.y)
        if not item:
            return
        # Select the item
        self.tree.selection_set(item)
        # Get connection ID
        conn_id = int(item)
        # Check if connection is active
        is_active = conn_id in self.active_connections

        # Create a custom menu using CTkFrame
        menu = ctk.CTkToplevel(self)
        menu.overrideredirect(True)  # Remove window decorations
        menu.geometry(f"+{event.x_root}+{event.y_root}")  # Position at mouse click
        menu_frame = ctk.CTkFrame(menu, fg_color=COLORS["bg_secondary"])
        menu_frame.pack(padx=5, pady=5)

        # Add menu items based on connection status

        ctk.CTkButton(
            menu_frame,
            text="Remove",
            command=lambda: [self.disconnect_selected(), self.remove_connection(conn_id), menu.destroy()],
            fg_color=COLORS["bg_primary"],
            hover_color=COLORS["accent_primary"]
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            menu_frame,
            text="File Transfer",
            command=lambda: [self.open_file_transfer(conn_id)],
            fg_color=COLORS["bg_primary"],
            hover_color=COLORS["accent_primary"]
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            menu_frame,
            text="Whoami",
            command=lambda: [self.send_specific_command("Whoami")],
            fg_color=COLORS["bg_primary"],
            hover_color=COLORS["accent_primary"]
        ).pack(fill="x", pady=2)




        # Improve auto-close behavior
        # 1. Close when focus is lost
        menu.bind("<FocusOut>", lambda e: menu.destroy())
        # 2. Close when mouse is clicked elsewhere
        menu.bind("<Button-1>", lambda e: menu.destroy(), add="+")
        self.bind("<Button-1>", lambda e: menu.destroy(), add="+")

        # Grab focus to ensure FocusOut works properly
        menu.focus_set()

        # Schedule destruction of temporary bindings
        self.after(100, lambda: self.unbind("<Button-1>", None))

    def open_file_transfer(self, conn_id):
        """Open file transfer window"""
        # Check if connection is active
        if conn_id not in self.active_connections:
            messagebox.showerror("Error", "Connection is not active")
            return
            
        try:
            # Create file transfer window
            transfer_window = ctk.CTkToplevel(self)
            transfer_window.title(f"File Transfer - Connection {conn_id}")
            transfer_window.geometry("600x400")
            transfer_window.minsize(500, 300)
            
            # Configure grid
            transfer_window.grid_columnconfigure(0, weight=1)
            transfer_window.grid_rowconfigure(0, weight=0)
            transfer_window.grid_rowconfigure(1, weight=1)
            transfer_window.grid_rowconfigure(2, weight=0)
            
            # Create header frame
            header_frame = ctk.CTkFrame(transfer_window, fg_color=COLORS["bg_secondary"])
            header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            
            # Connection info
            ip = self.connection_info[conn_id]["ip"]
            port = self.connection_info[conn_id]["port"]
            
            conn_label = ctk.CTkLabel(header_frame, text=f"Connection: {ip}:{port}", text_color=COLORS["text_accent"])
            conn_label.pack(side="left", padx=10, pady=10)
            
            # Create tabview
            tabview = ctk.CTkTabview(transfer_window, fg_color=COLORS["bg_primary"])
            tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            
            # Add tabs
            tabview.add("Upload")
            tabview.add("Download")
            
            # Upload tab
            upload_frame = ctk.CTkFrame(tabview.tab("Upload"), fg_color=COLORS["bg_secondary"])
            upload_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            upload_label = ctk.CTkLabel(upload_frame, text="Select files to upload:", text_color=COLORS["text_primary"])
            upload_label.pack(anchor="w", padx=10, pady=10)
            
            upload_btn = ctk.CTkButton(upload_frame, text="Browse Files",
                                     command=lambda: self.select_upload_files(conn_id), 
                                     fg_color=COLORS["accent_primary"], 
                                     hover_color=COLORS["accent_secondary"],
                                     text_color=COLORS["text_primary"])
            upload_btn.pack(anchor="w", padx=10, pady=10)
            
            # Download tab
            download_frame = ctk.CTkFrame(tabview.tab("Download"), fg_color=COLORS["bg_secondary"])
            download_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            download_label = ctk.CTkLabel(download_frame, text="Remote file path:", text_color=COLORS["text_primary"])
            download_label.pack(anchor="w", padx=10, pady=10)
            
            path_frame = ctk.CTkFrame(download_frame, fg_color=COLORS["bg_secondary"])
            path_frame.pack(fill="x", padx=10, pady=10)
            
            path_entry = ctk.CTkEntry(path_frame, placeholder_text="Enter remote file path", 
                                    border_color=COLORS["border"], text_color=COLORS["text_primary"])
            path_entry.pack(side="left", fill="x", expand=True, padx=5)
            
            download_btn = ctk.CTkButton(path_frame, text="Download",
                                       command=lambda: self.download_file(conn_id, path_entry.get()), 
                                       fg_color=COLORS["accent_primary"], 
                                       hover_color=COLORS["accent_secondary"],
                                       text_color=COLORS["text_primary"])
            download_btn.pack(side="left", padx=5)
            
            # Status frame
            status_frame = ctk.CTkFrame(transfer_window, fg_color=COLORS["bg_secondary"])
            status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
            
            status_label = ctk.CTkLabel(status_frame, text="Ready", text_color=COLORS["text_secondary"])
            status_label.pack(side="left", padx=10, pady=5)
            
            progress_bar = ctk.CTkProgressBar(status_frame, width=200)
            progress_bar.pack(side="right", padx=10, pady=5)
            progress_bar.set(0)
            
            # Store references
            transfer_window.status_label = status_label
            transfer_window.progress_bar = progress_bar
            
        except Exception as e:
            self.update_console(f"[-] Error opening file transfer window: {e}", "error")
            
    def disconnect_selected(self):
        """Disconnect selected connection"""
        # Get selected item
        selection = self.tree.selection()
        if not selection:
            return
            
        # Get connection ID
        conn_id = int(selection[0])
            
        try:
            # Send exit command
            self.connection_sockets[conn_id].send("exit".encode())
            
            # Log command to database
            if conn_id in self.connection_db_ids:
                self.db.log_message(self.connection_db_ids[conn_id], "exit", "sent")
                
            # Close socket
            self.connection_sockets[conn_id].close()
            
            # Handle disconnection
            self.handle_disconnection(conn_id)
            
        except Exception as e:
            self.update_console(f"[-] Error disconnecting: {e}", "error")

    def remove_connection(self, conn_id):
        """Remove connection from treeview"""
        try:
            # Remove from treeview
            self.tree.delete(str(conn_id))
            
            # Remove from screen share tab if it exists
            #if hasattr(self, 'screen_share_tab') and conn_id in self.screen_share_tab.ip_frames:
                # Remove from screen share tab
            #    self.screen_share_tab.ip_frames[conn_id]["frame"].destroy()
            #    del self.screen_share_tab.ip_frames[conn_id]

            if hasattr(self, 'screen_share_tab'):
                self.screen_share_tab.connection_removed(conn_id)
            
            # Update console
            self.update_console(f"[-] Connection {conn_id} removed", "info")
            
        except Exception as e:
            self.update_console(f"[-] Error removing connection: {e}", "error")

    def view_screen(self, conn_id, custom_video_label=None):
        """View screen of selected connection"""
        # Check if connection is active
        if conn_id not in self.active_connections:
            messagebox.showerror("Error", "Connection is not active")
            return
            
        # If using screen share tab with custom video label
        if custom_video_label is not None:
            try:
                # Start screen streaming server if not already running
                if self.stream_server_socket is None:
                    self.start_stream_server()
                
                # Send screen streaming command
                self.connection_sockets[conn_id].send("start_stream".encode())
                
                # Log command to database
                if conn_id in self.connection_db_ids:
                    self.db.log_message(self.connection_db_ids[conn_id], "screen_stream", "sent")
                
                # Set streaming active flag
                self.streaming_active = True
                
                # Start screen streaming thread with custom label
                threading.Thread(target=self.receive_screen_stream, 
                                args=(conn_id, custom_video_label), 
                                daemon=True).start()
                
                # Update console
                self.update_console(f"[+] Screen streaming started for connection {conn_id} in Screen Share tab", "success")
                
                return
            except Exception as e:
                self.update_console(f"[-] Error starting screen streaming in tab: {e}", "error")
                return
        
        # Check if screen streaming is already active for this connection in a window
        if conn_id in self.stream_windows and self.stream_windows[conn_id].winfo_exists():
            # Bring window to front
            self.stream_windows[conn_id].lift()
            self.stream_windows[conn_id].focus_force()
            return
            
        try:
            # Start screen streaming server if not already running
            if self.stream_server_socket is None:
                self.start_stream_server()
                
            # Send screen streaming command
            self.connection_sockets[conn_id].send("start_stream".encode())
            
            # Log command to database
            if conn_id in self.connection_db_ids:
                self.db.log_message(self.connection_db_ids[conn_id], "screen_stream", "sent")
                
            # Create screen streaming window
            stream_window = ctk.CTkToplevel(self)
            stream_window.title(f"Screen Stream - Connection {conn_id}")
            stream_window.geometry("800x600")
            stream_window.minsize(400, 300)
            
            # Store window reference
            self.stream_windows[conn_id] = stream_window
            
            # Configure grid
            stream_window.grid_columnconfigure(0, weight=1)
            stream_window.grid_rowconfigure(0, weight=1)
            stream_window.grid_rowconfigure(1, weight=0)
            
            # Create screen frame
            screen_frame = ctk.CTkFrame(stream_window, fg_color=COLORS["bg_secondary"])
            screen_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            
            # Create video label
            video_label = tk.Label(screen_frame, bg=COLORS["bg_primary"])
            video_label.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create control frame
            control_frame = ctk.CTkFrame(stream_window, fg_color=COLORS["bg_secondary"])
            control_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
            
            # Create stop button
            stop_btn = ctk.CTkButton(control_frame, text="Stop Streaming",
                                   command=lambda: self.stop_streaming(conn_id), 
                                   fg_color=COLORS["accent_danger"], 
                                   hover_color="#CC3D3D",
                                   text_color=COLORS["text_primary"])
            stop_btn.pack(side="left", padx=10, pady=10)
            
            # Create screenshot button
            screenshot_btn = ctk.CTkButton(control_frame, text="Take Screenshot",
                                        command=lambda: self.take_screenshot(conn_id), 
                                        fg_color=COLORS["accent_primary"], 
                                        hover_color=COLORS["accent_secondary"],
                                        text_color=COLORS["text_primary"])
            screenshot_btn.pack(side="left", padx=10, pady=10)
            
            # Create quality slider
            quality_frame = ctk.CTkFrame(control_frame, fg_color=COLORS["bg_secondary"])
            quality_frame.pack(side="right", padx=10, pady=10)
            
            quality_label = ctk.CTkLabel(quality_frame, text="Quality:", text_color=COLORS["text_accent"])
            quality_label.pack(side="left", padx=5)
            
            quality_var = ctk.IntVar(value=50)
            quality_slider = ctk.CTkSlider(quality_frame, from_=10, to=100, variable=quality_var,
                                        command=lambda value: self.update_stream_quality(conn_id, int(value)),
                                        fg_color=COLORS["bg_primary"],
                                        progress_color=COLORS["accent_primary"],
                                        button_color=COLORS["accent_secondary"],
                                        button_hover_color=COLORS["accent_primary"],
                                        width=150)
            quality_slider.pack(side="left", padx=5)
            
            quality_value = ctk.CTkLabel(quality_frame, text="50%", text_color=COLORS["text_primary"])
            quality_slider.configure(command=lambda value: [self.update_stream_quality(conn_id, int(value)), 
                                                         quality_value.configure(text=f"{int(value)}%")])
            quality_value.pack(side="left", padx=5)
            
            # Create FPS slider
            fps_frame = ctk.CTkFrame(control_frame, fg_color=COLORS["bg_secondary"])
            fps_frame.pack(side="right", padx=10, pady=10)
            
            fps_label = ctk.CTkLabel(fps_frame, text="FPS:", text_color=COLORS["text_accent"])
            fps_label.pack(side="left", padx=5)
            
            fps_var = ctk.IntVar(value=10)
            fps_slider = ctk.CTkSlider(fps_frame, from_=1, to=30, variable=fps_var,
                                     command=lambda value: self.update_stream_fps(conn_id, int(value)),
                                     fg_color=COLORS["bg_primary"],
                                     progress_color=COLORS["accent_primary"],
                                     button_color=COLORS["accent_secondary"],
                                     button_hover_color=COLORS["accent_primary"],
                                     width=150)
            fps_slider.pack(side="left", padx=5)
            
            fps_value = ctk.CTkLabel(fps_frame, text="10 FPS", text_color=COLORS["text_primary"])
            fps_slider.configure(command=lambda value: [self.update_stream_fps(conn_id, int(value)), 
                                                     fps_value.configure(text=f"{int(value)} FPS")])
            fps_value.pack(side="left", padx=5)
            
            # Store references
            self.screen_frame = screen_frame
            self.video_label = video_label
            self.streaming_active = True
            self.screen_socket = self.connection_sockets[conn_id]
            
            # Handle window close
            stream_window.protocol("WM_DELETE_WINDOW", lambda: self.stop_streaming(conn_id))
            
            # Start screen streaming thread
            threading.Thread(target=self.receive_screen_stream, args=(conn_id, video_label), daemon=True).start()
            
            # Update console
            self.update_console(f"[+] Screen streaming started for connection {conn_id}", "success")
            
        except Exception as e:
            self.update_console(f"[-] Error starting screen streaming: {e}", "error")

    def receive_screen_stream(self, conn_id, video_label):
        """Receive screen stream from client"""
        try:
            # Get socket
            client_socket = self.connection_sockets[conn_id]
            
            # Set larger buffer size for streaming
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            
            # Receive screen stream
            buffer = b""
            frame_size = 0
            
            while conn_id in self.active_connections and self.streaming_active:
                try:
                    # Receive data
                    data = client_socket.recv(1024 * 1024)
                    if not data:
                        break
                        
                    # Add to buffer
                    buffer += data
                    
                    # Process frames
                    while True:
                        # If we don't have the frame size yet, try to get it
                        if frame_size == 0 and len(buffer) >= 4:
                            frame_size = struct.unpack("!I", buffer[:4])[0]
                            buffer = buffer[4:]
                            
                        # If we have the frame size, check if we have a complete frame
                        if frame_size > 0 and len(buffer) >= frame_size:
                            # Extract frame data
                            frame_data = buffer[:frame_size]
                            buffer = buffer[frame_size:]
                            
                            # Reset frame size
                            frame_size = 0
                            
                            # Process frame
                            try:
                                # Decode image
                                img = Image.open(BytesIO(frame_data))
                                
                                # Resize image if needed
                                if self.stream_scale_x != 1.0 or self.stream_scale_y != 1.0:
                                    new_width = int(img.width * self.stream_scale_x)
                                    new_height = int(img.height * self.stream_scale_y)
                                    img = img.resize((new_width, new_height), Image.LANCZOS)
                                    
                                # Convert to PhotoImage
                                photo = ImageTk.PhotoImage(img)
                                
                                # Update label
                                video_label.config(image=photo)
                                video_label.image = photo
                                
                                # Update screen share tab preview if it exists
                                if hasattr(self, 'screen_share_tab'):
                                    try:
                                        self.screen_share_tab.connection_added(conn_id)
                                        # Convert PIL image to numpy array for the screen share tab
                                        frame_array = np.array(img)
                                        # Convert RGB to BGR for OpenCV compatibility
                                        frame_array = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
                                        self.screen_share_tab.update_preview(conn_id, frame_array)
                                    except Exception as e:
                                        self.update_console(f"[-] Error updating preview: {e}", "error")
                                
                            except Exception as e:
                                print(f"Error processing frame: {e}")
                                
                        else:
                            # Not enough data for a complete frame
                            break
                            
                except socket.timeout:
                    continue
                    
                except Exception as e:
                    print(f"Error receiving screen stream: {e}")
                    break
                    
            # Clean up
            video_label.config(image="")
            
        except Exception as e:
            self.update_console(f"[-] Error in screen streaming: {e}", "error")

    def stop_streaming(self, conn_id):
        """Stop screen streaming"""
        try:
            # Set streaming inactive
            self.streaming_active = False
            
            # Send stop command
            if conn_id in self.connection_sockets:
                self.connection_sockets[conn_id].send("stop_stream".encode())
                
                # Log command to database
                if conn_id in self.connection_db_ids:
                    self.db.log_message(self.connection_db_ids[conn_id], "stop_stream", "sent")
                    
            # Close window
            if conn_id in self.stream_windows and self.stream_windows[conn_id].winfo_exists():
                self.stream_windows[conn_id].destroy()
                
            # Update console
            self.update_console(f"[-] Screen streaming stopped for connection {conn_id}", "info")
            
        except Exception as e:
            self.update_console(f"[-] Error stopping screen streaming: {e}", "error")

    def take_screenshot(self, conn_id):
        """Take screenshot from stream"""
        try:
            # Check if streaming is active
            if not self.streaming_active:
                messagebox.showerror("Error", "Screen streaming is not active")
                return
                
            # Get current image
            if hasattr(self.video_label, "image") and self.video_label.image:
                # Get save path
                save_path = filedialog.asksaveasfilename(defaultextension=".png", 
                                                       filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
                if not save_path:
                    return
                    
                # Save image
                img = ImageTk.getimage(self.video_label.image)
                img.save(save_path)
                
                # Update console
                self.update_console(f"[+] Screenshot saved to {save_path}", "success")
                
            else:
                messagebox.showerror("Error", "No image available")
                
        except Exception as e:
            self.update_console(f"[-] Error taking screenshot: {e}", "error")

    def update_stream_quality(self, conn_id, quality):
        """Update stream quality"""
        try:
            # Send quality command
            if conn_id in self.connection_sockets:
                self.connection_sockets[conn_id].send(f"stream_quality {quality}".encode())
                
        except Exception as e:
            self.update_console(f"[-] Error updating stream quality: {e}", "error")

    def update_stream_fps(self, conn_id, fps):
        """Update stream FPS"""
        try:
            # Send FPS command
            if conn_id in self.connection_sockets:
                self.connection_sockets[conn_id].send(f"stream_fps {fps}".encode())
                
        except Exception as e:
            self.update_console(f"[-] Error updating stream FPS: {e}", "error")

    def open_file_transfer(self, conn_id):
        """Open file transfer window"""
        # Check if connection is active
        if conn_id not in self.active_connections:
            messagebox.showerror("Error", "Connection is not active")
            return
            
        try:
            # Create file transfer window
            transfer_window = ctk.CTkToplevel(self)
            transfer_window.title(f"File Transfer - Connection {conn_id}")
            transfer_window.geometry("600x400")
            transfer_window.minsize(500, 300)
            
            # Configure grid
            transfer_window.grid_columnconfigure(0, weight=1)
            transfer_window.grid_rowconfigure(0, weight=0)
            transfer_window.grid_rowconfigure(1, weight=1)
            transfer_window.grid_rowconfigure(2, weight=0)
            
            # Create header frame
            header_frame = ctk.CTkFrame(transfer_window, fg_color=COLORS["bg_secondary"])
            header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            
            # Connection info
            ip = self.connection_info[conn_id]["ip"]
            port = self.connection_info[conn_id]["port"]
            
            conn_label = ctk.CTkLabel(header_frame, text=f"Connection: {ip}:{port}", text_color=COLORS["text_accent"])
            conn_label.pack(side="left", padx=10, pady=10)
            
            # Create tabview
            tabview = ctk.CTkTabview(transfer_window, fg_color=COLORS["bg_primary"])
            tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            
            # Add tabs
            tabview.add("Upload")
            tabview.add("Download")
            
            # Upload tab
            upload_frame = ctk.CTkFrame(tabview.tab("Upload"), fg_color=COLORS["bg_secondary"])
            upload_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            upload_label = ctk.CTkLabel(upload_frame, text="Select files to upload:", text_color=COLORS["text_primary"])
            upload_label.pack(anchor="w", padx=10, pady=10)
            
            upload_btn = ctk.CTkButton(upload_frame, text="Browse Files",
                                     command=lambda: self.select_upload_files(conn_id), 
                                     fg_color=COLORS["accent_primary"], 
                                     hover_color=COLORS["accent_secondary"],
                                     text_color=COLORS["text_primary"])
            upload_btn.pack(anchor="w", padx=10, pady=10)
            
            # Download tab
            download_frame = ctk.CTkFrame(tabview.tab("Download"), fg_color=COLORS["bg_secondary"])
            download_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            download_label = ctk.CTkLabel(download_frame, text="Remote file path:", text_color=COLORS["text_primary"])
            download_label.pack(anchor="w", padx=10, pady=10)
            
            path_frame = ctk.CTkFrame(download_frame, fg_color=COLORS["bg_secondary"])
            path_frame.pack(fill="x", padx=10, pady=10)
            
            path_entry = ctk.CTkEntry(path_frame, placeholder_text="Enter remote file path", 
                                    border_color=COLORS["border"], text_color=COLORS["text_primary"])
            path_entry.pack(side="left", fill="x", expand=True, padx=5)
            
            download_btn = ctk.CTkButton(path_frame, text="Download",
                                       command=lambda: self.download_file(conn_id, path_entry.get()), 
                                       fg_color=COLORS["accent_primary"], 
                                       hover_color=COLORS["accent_secondary"],
                                       text_color=COLORS["text_primary"])
            download_btn.pack(side="left", padx=5)
            
            # Status frame
            status_frame = ctk.CTkFrame(transfer_window, fg_color=COLORS["bg_secondary"])
            status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
            
            status_label = ctk.CTkLabel(status_frame, text="Ready", text_color=COLORS["text_secondary"])
            status_label.pack(side="left", padx=10, pady=5)
            
            progress_bar = ctk.CTkProgressBar(status_frame, width=200)
            progress_bar.pack(side="right", padx=10, pady=5)
            progress_bar.set(0)
            
            # Store references
            transfer_window.status_label = status_label
            transfer_window.progress_bar = progress_bar
            
        except Exception as e:
            self.update_console(f"[-] Error opening file transfer window: {e}", "error")

    def select_upload_files(self, conn_id):
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
        threading.Thread(target=self.upload_file, args=(conn_id, local_path, file_name_remote), daemon=True).start()

    def upload_file(self, connection_name, local_path, file_name_remote):
        try:
            self.connection_sockets[connection_name].send(f"download {file_name_remote}".encode())
        except Exception as e:
            self.log_message(connection_name, f"Error uploading file: {str(e)}", "error")

    def download_file(self, conn_id, remote_path):
        """Download file from client"""
        try:
            # Check if connection is active
            if conn_id not in self.active_connections:
                messagebox.showerror("Error", "Connection is not active")
                return
                
            # Check if path is provided
            if not remote_path:
                messagebox.showerror("Error", "Please enter a remote file path")
                return
                
            # Get save path
            file_name = os.path.basename(remote_path)
            save_path = filedialog.asksaveasfilename(defaultextension=".*", 
                                                   filetypes=[("All files", "*.*")],
                                                   initialfile=file_name)
            if not save_path:
                return
                
            # Update console
            self.update_console(f"[+] Downloading {remote_path} from connection {conn_id}", "info")
            
            # Send download command
            self.connection_sockets[conn_id].send(f"upload {remote_path}".encode())
            
            # Log command to database
            if conn_id in self.connection_db_ids:
                self.db.log_message(self.connection_db_ids[conn_id], f"download {remote_path}", "sent")
                ip_address = self.connection_info[conn_id]["ip"]
                self.db.log_message(conn_id, f"Attempting to download from IP: {ip_address}", "info")
                file_name = os.path.basename(remote_path)
                file_name = file_name.replace("\\", "")
                file_name = requests.utils.quote(file_name)
                url = f"http://{ip_address}:8080/{file_name}"
                self.db.log_message(conn_id, f"Download URL: {url}", "info")
                response = requests.get(url, stream=True)
                if response.status_code == 200:
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    self.db.log_message(conn_id, f"File downloaded successfully: {save_path}", "success")
                else:
                    self.db.log_message(conn_id, f"Failed to download file: HTTP {response.status_code}", "error")







                # Update console
                self.update_console(f"[+] Download completed: {save_path}", "success")
                
            else:
                self.update_console(f"[-] Download failed: Unexpected response", "error")
                
        except Exception as e:
            self.update_console(f"[-] Error downloading file: {e}", "error")

    def format_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def get_system_info(self, conn_id):
        """Get system info from client"""
        try:
            # Check if connection is active
            if conn_id not in self.active_connections:
                messagebox.showerror("Error", "Connection is not active")
                return
                
            # Send command
            self.connection_sockets[conn_id].send("sysinfo".encode())
            
            # Log command to database
            if conn_id in self.connection_db_ids:
                self.db.log_message(self.connection_db_ids[conn_id], "sysinfo", "sent")
                
            # Update console
            self.update_console(f"[+] Getting system info from connection {conn_id}", "info")
            
        except Exception as e:
            self.update_console(f"[-] Error getting system info: {e}", "error")

    def get_process_list(self, conn_id):
        """Get process list from client"""
        try:
            # Check if connection is active
            if conn_id not in self.active_connections:
                messagebox.showerror("Error", "Connection is not active")
                return
                
            # Send command
            self.connection_sockets[conn_id].send("ps".encode())
            
            # Log command to database
            if conn_id in self.connection_db_ids:
                self.db.log_message(self.connection_db_ids[conn_id], "ps", "sent")
                
            # Update console
            self.update_console(f"[+] Getting process list from connection {conn_id}", "info")
            
        except Exception as e:
            self.update_console(f"[-] Error getting process list: {e}", "error")

    def get_network_info(self, conn_id):
        """Get network info from client"""
        try:
            # Check if connection is active
            if conn_id not in self.active_connections:
                messagebox.showerror("Error", "Connection is not active")
                return
                
            # Send command
            self.connection_sockets[conn_id].send("netstat".encode())
            
            # Log command to database
            if conn_id in self.connection_db_ids:
                self.db.log_message(self.connection_db_ids[conn_id], "netstat", "sent")
                
            # Update console
            self.update_console(f"[+] Getting network info from connection {conn_id}", "info")
            
        except Exception as e:
            self.update_console(f"[-] Error getting network info: {e}", "error")

    def stop_all_listeners(self):
        """Stop all listeners"""
        try:

            # Close all connections
            for conn_id in list(self.active_connections):
                try:
                    # Send exit command
                    self.connection_sockets[conn_id].send("exit".encode())
                    
                    # Log command to database
                    if conn_id in self.connection_db_ids:
                        self.db.log_message(self.connection_db_ids[conn_id], "exit", "sent")
                        
                    # Close socket
                    self.connection_sockets[conn_id].close()
                    
                    # Handle disconnection
                    self.handle_disconnection(conn_id)
                    
                except:
                    pass

            # Confirm stop
            if not messagebox.askyesno("Confirm", "Are you sure you want to stop all listeners?"):
                return
                    
            # Close all listeners
            for port, listener in self.listeners.items():
                try:
                    listener.close()
                except:
                    pass
                    
            # Clear listeners
            self.listeners.clear()
            self.main_listener = None
            
            # Update UI
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_indicator.configure(text="●", text_color="#ff0000")
            self.status_text.configure(text="Offline")
            
            # Update console
            self.update_console("[-] All listeners stopped", "warning")
            
        except Exception as e:
            self.update_console(f"[-] Error stopping listeners: {e}", "error")

    def on_closing(self):
        """Handle window closing"""
        try:
            # Confirm exit
            if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
                # Stop all listeners
                for port, listener in self.listeners.items():
                    try:
                        listener.close()
                    except:
                        pass
                        
                # Close all connections
                for conn_id in self.active_connections:
                    try:
                        self.connection_sockets[conn_id].close()
                    except:
                        pass
                        
                # Close database
                self.db.close_all_connections()
                
                # Destroy window
                self.destroy()
                
        except Exception as e:
            print(f"Error closing: {e}")
            self.destroy()

    def start_stream_server(self):
        """Start a server to receive screen streaming connections"""
        try:
            # Create socket
            self.stream_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.stream_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to port
            self.stream_server_socket.bind(('0.0.0.0', self.stream_server_port))
            
            # Listen for connections
            self.stream_server_socket.listen(5)
            
            # Update console
            self.update_console(f"[+] Screen streaming server started on port {self.stream_server_port}", "success")
            
            # Start thread to accept connections
            threading.Thread(target=self.accept_stream_connections, daemon=True).start()
            
        except Exception as e:
            self.update_console(f"[-] Error starting screen streaming server: {e}", "error")
            self.stream_server_socket = None

    def accept_stream_connections(self):
        """Accept incoming screen streaming connections"""
        try:
            while self.stream_server_socket:
                try:
                    # Accept connection
                    client_socket, address = self.stream_server_socket.accept()
                    
                    # Set timeout
                    client_socket.settimeout(5.0)
                    
                    # Update console
                    self.update_console(f"[+] Screen streaming connection accepted from {address[0]}:{address[1]}", "success")
                    
                    # Store socket for later use
                    # We don't need to do anything with this connection here
                    # The receive_screen_stream method will handle the data
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.stream_server_socket:
                        self.update_console(f"[-] Error accepting screen streaming connection: {e}", "error")
                    else:
                        # Server was stopped
                        break
        except Exception as e:
            self.update_console(f"[-] Error in screen streaming server: {e}", "error")

if __name__ == "__main__":
    app = NcatGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

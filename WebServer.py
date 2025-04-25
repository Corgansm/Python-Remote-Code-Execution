# --- START OF FILE WebServer.py ---

import http.server
import socketserver
import os
import subprocess
import urllib.parse
import html
import io
# import cgi # <--- REMOVED THIS IMPORT
import time
from datetime import datetime
import shutil # For file copy on upload (kept for list_directory)
import json

# --- Configuration ---
HOST = "0.0.0.0"  # Listen on all available interfaces
PORT = 8080       # Default port if 80 fails
INITIAL_CWD = os.getcwd() # Directory where the script starts

# --- Helper Functions ---
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

# --- Custom Request Handler ---
class WebServerRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to add shell execution and manage CWD for the shell."""

    shell_current_directory = INITIAL_CWD

    def _send_headers(self, status_code, content_type="text/html; charset=utf-8", extra_headers=None):
        """Helper to send common headers."""
        self.send_response(status_code)
        self.send_header("Content-type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()

    def _serve_shell_html(self):
        """Serves the HTML page for the web shell."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Web Shell</title>
            <style>
                body {{ font-family: sans-serif; background-color: #f0f0f0; margin: 20px; }}
                .container {{ background-color: #fff; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                #output {{
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    padding: 15px;
                    border-radius: 4px;
                    min-height: 200px;
                    max-height: 500px;
                    overflow-y: auto;
                    font-family: monospace;
                    margin-top: 15px;
                }}
                input[type="text"] {{
                    width: calc(100% - 90px);
                    padding: 8px;
                    margin-right: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }}
                button {{
                    padding: 8px 15px;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
                button:hover {{ background-color: #0056b3; }}
                .path-display {{ margin-bottom: 10px; font-style: italic; color: #555; }}
                /* #upload-form removed */
                #file-browser-link {{ display: block; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Web Shell</h2>
                <div class="path-display">Current Path: <span id="currentPath">{html.escape(self.shell_current_directory)}</span></div>
                <form id="shell-form" method="POST" action="/execute">
                    <input type="text" name="command" id="command-input" placeholder="Enter command..." autofocus>
                    <button type="submit">Execute</button>
                </form>
                <h3>Output:</h3>
                <pre id="output">[Output will appear here]</pre>

                <!-- Upload Form Removed -->
                <!--
                <div id="upload-form">
                    <h3>Upload File</h3>
                     <form action="/upload" method="post" enctype="multipart/form-data">
                        <input type="file" name="file_to_upload" required>
                        <input type="hidden" name="target_dir" value="{html.escape(self.shell_current_directory)}">
                        <button type="submit">Upload</button>
                    </form>
                </div>
                -->

                <a href="/" id="file-browser-link">Return to File Browser</a>
            </div>

            <script>
                const form = document.getElementById('shell-form');
                const input = document.getElementById('command-input');
                const outputArea = document.getElementById('output');
                const pathDisplay = document.getElementById('currentPath');

                form.addEventListener('submit', async (event) => {{
                    event.preventDefault(); // Prevent default form submission
                    const command = input.value;
                    input.value = ''; // Clear input field

                    // Append command to output visually
                    outputArea.textContent += `\\n> ${{command}}\\n`;
                    outputArea.scrollTop = outputArea.scrollHeight; // Scroll to bottom

                    try {{
                        const response = await fetch('/execute', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/x-www-form-urlencoded',
                            }},
                            body: `command=${{encodeURIComponent(command)}}`
                        }});

                        if (!response.ok) {{
                            throw new Error(`HTTP error! status: ${{response.status}}`);
                        }}

                        const result = await response.json(); // Expect JSON response

                        // Update output area
                        outputArea.textContent += result.output;
                        // Update path display
                        pathDisplay.textContent = result.cwd;
                        outputArea.scrollTop = outputArea.scrollHeight; // Scroll again

                    }} catch (error) {{
                        outputArea.textContent += `\\nError: ${{error.message}}`;
                        outputArea.scrollTop = outputArea.scrollHeight;
                    }}
                }});
            </script>
        </body>
        </html>
        """
        encoded_html = html_content.encode('utf-8')
        self._send_headers(200)
        self.wfile.write(encoded_html)

    def _execute_command(self, command):
        """Executes a shell command and returns output and new CWD."""
        output = ""
        try:
            if command.strip().startswith("cd"):
                new_dir_part = command.strip()[len("cd"):].strip()
                # Handle potential quotes
                if len(new_dir_part) > 1 and new_dir_part.startswith('"') and new_dir_part.endswith('"'):
                    new_dir_part = new_dir_part[1:-1]
                elif len(new_dir_part) > 1 and new_dir_part.startswith("'") and new_dir_part.endswith("'"):
                    new_dir_part = new_dir_part[1:-1]

                if not new_dir_part: # "cd" without args - go to initial dir? Or just report current?
                     output = f"Current directory: {self.shell_current_directory}\n"
                     # Keep shell_current_directory as is
                else:
                    # Attempt to change directory
                    target_path = os.path.abspath(os.path.join(self.shell_current_directory, new_dir_part))

                    if os.path.isdir(target_path):
                        WebServerRequestHandler.shell_current_directory = target_path
                        output = f"Changed directory to: {self.shell_current_directory}\n"
                    else:
                        output = f"Error: Directory not found or not a directory: {target_path}\n"
            else:
                # Execute other commands
                result = subprocess.run(
                    command,
                    shell=True, # SECURITY RISK! Be very careful.
                    capture_output=True,
                    text=True,
                    errors='ignore',
                    cwd=self.shell_current_directory, # Execute in the shell's CWD
                    timeout=30 # Add a timeout
                )
                output = result.stdout + result.stderr
                if not output.strip() and result.returncode == 0:
                     output = f"[+] Command '{command}' executed successfully (no output).\n"
                elif result.returncode != 0:
                     output += f"[!] Command exited with code {result.returncode}.\n"

        except subprocess.TimeoutExpired:
            output = f"Error: Command '{command}' timed out after 30 seconds.\n"
        except Exception as e:
            output = f"Error executing command '{command}': {str(e)}\n"

        # Return both output and the potentially updated CWD
        return {"output": output, "cwd": self.shell_current_directory}

    def do_GET(self):
        """Handle GET requests for files, directories, and the shell page."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query = parsed_path.query

        print(f"GET request: Path='{path}', Query='{query}'")

        if path == '/shell':
            self._serve_shell_html()
            return
        elif path == '/favicon.ico':
             self.send_error(404, "File not found")
             return
        elif path == '/execute':
             # Handle command execution via GET (less ideal than POST, but for simplicity)
             params = urllib.parse.parse_qs(query)
             command = params.get('command', [None])[0]
             if command:
                  result = self._execute_command(command)
                  self._send_headers(200, content_type="application/json")
                  self.wfile.write(json.dumps(result).encode('utf-8')) # Use json.dumps
             else:
                  self.send_error(400, "Missing 'command' parameter")
             return

        # If not a special path, treat as file/directory request relative to INITIAL_CWD
        super().do_GET()

    def do_POST(self):
        """Handle POST requests, specifically for shell commands."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        print(f"POST request: Path='{path}'")

        if path == '/execute':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data_bytes = self.rfile.read(content_length)
            post_data_str = post_data_bytes.decode('utf-8')
            params = urllib.parse.parse_qs(post_data_str)
            command = params.get('command', [None])[0]

            if command:
                result = self._execute_command(command)
                self._send_headers(200, content_type="application/json")
                self.wfile.write(json.dumps(result).encode('utf-8'))
            else:
                self._send_headers(400, content_type="application/json")
                self.wfile.write(b'{"error": "Missing command"}')
            return

        # --- Upload handling removed ---
        # elif path == '/upload':
        #      self.handle_upload() # This method no longer exists
        #      return

        # Handle other POST requests
        self.send_error(405, "Method Not Allowed")


    # --- handle_upload method REMOVED ---
    # def handle_upload(self):
    #     ... (code using cgi.FieldStorage was here) ...


    def list_directory(self, path):
        """Generate HTML for a directory listing."""
        try:
            list_dir = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None
        list_dir.sort(key=lambda a: a.lower())

        f = io.BytesIO()
        displaypath = html.escape(urllib.parse.unquote(self.path), quote=False)
        f.write(b'<!DOCTYPE html>\n')
        f.write(b'<html>\n<head>\n')
        f.write(b'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">') # Corrected line
        f.write(b'<title>Directory listing for %s</title>\n' % displaypath.encode())
        f.write(b'<style>\n')
        f.write(b'body { font-family: sans-serif; padding: 20px; }\n')
        f.write(b'table { border-collapse: collapse; width: 80%; margin-top: 15px; }\n')
        f.write(b'th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }\n')
        f.write(b'th { background-color: #f2f2f2; }\n')
        f.write(b'a { text-decoration: none; color: #007bff; }\n')
        f.write(b'a:hover { text-decoration: underline; }\n')
        f.write(b'.shell-link { margin-top: 20px; display: block; }\n')
        f.write(b'</style>\n')
        f.write(b'</head>\n<body>\n')
        f.write(b'<h2>Directory listing for %s</h2>\n' % displaypath.encode())
        f.write(b'<a href="/shell" class="shell-link">Go to Web Shell</a><hr>\n')

        f.write(b'<table>\n')
        f.write(b'<tr><th>Name</th><th>Size</th><th>Modified</th></tr>\n')

        if os.path.abspath(path) != os.path.abspath(INITIAL_CWD):
            parent_web_path = urllib.parse.urljoin(self.path, '..')
            f.write(b'<tr><td><a href="%s">.. (Parent Directory)</a></td><td>-</td><td>-</td></tr>\n' % urllib.parse.quote(parent_web_path).encode())


        for name in list_dir:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            is_dir = os.path.isdir(fullname)
            if is_dir:
                displayname = name + "/"
                linkname = name + "/"
                size_str = "-"
                mod_time_str = "-"
            else:
                try:
                    stat_result = os.stat(fullname)
                    size_str = format_size(stat_result.st_size)
                    mod_time_str = datetime.fromtimestamp(stat_result.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                except OSError:
                    size_str = "N/A"
                    mod_time_str = "N/A"

            f.write(b'<tr>')
            f.write(b'<td><a href="%s">%s</a></td>' % (urllib.parse.quote(linkname).encode(), html.escape(displayname).encode()))
            f.write(b'<td>%s</td>' % size_str.encode())
            f.write(b'<td>%s</td>' % mod_time_str.encode())
            f.write(b'</tr>\n')
        f.write(b'</table>\n')
        f.write(b'<hr></body>\n</html>\n')

        length = f.tell()
        f.seek(0)
        self._send_headers(200, extra_headers={"Content-Length": str(length)})
        shutil.copyfileobj(f, self.wfile)
        f.close()
        return None


# --- Main Execution ---
if __name__ == "__main__":
    if not os.path.isdir(WebServerRequestHandler.shell_current_directory):
        print(f"Warning: Initial shell directory '{WebServerRequestHandler.shell_current_directory}' not found. Falling back to script directory.")
        WebServerRequestHandler.shell_current_directory = os.path.dirname(os.path.abspath(__file__)) or '.'

    try:
        server_port = 8080
        class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            pass
        httpd = ThreadingHTTPServer((HOST, server_port), WebServerRequestHandler)
    except OSError as e:
        if e.errno == 10013: # WSAEACCES (Permission denied)
             print(f"Warning: Could not bind to port 80 (Permission denied). Trying port {PORT} instead.")
             server_port = PORT
             httpd = ThreadingHTTPServer((HOST, server_port), WebServerRequestHandler)
        else:
             print(f"[ERROR] Could not start server on port 80: {e}")
             exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to start server: {e}")
        exit(1)


    print(f"Serving HTTP on {HOST}:{server_port}...")
    print(f"File browsing relative to: {INITIAL_CWD}")
    print(f"Initial shell directory:   {WebServerRequestHandler.shell_current_directory}")
    print(f"Access file browser at: http://<your_ip>:{server_port}/")
    print(f"Access web shell at:    http://<your_ip>:{server_port}/shell")
    print("--- WARNING: THIS SERVER IS INSECURE ---")
    print("--- DO NOT EXPOSE TO UNTRUSTED NETWORKS ---")


    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received, shutting down server.")
        httpd.server_close()
    except Exception as e:
        print(f"\n[ERROR] Server encountered an error: {e}")
        try:
            httpd.server_close()
        except Exception: pass
    finally:
        print("[INFO] Server stopped.")
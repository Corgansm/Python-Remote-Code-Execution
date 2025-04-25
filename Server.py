import os
from flask import Flask, send_from_directory, render_template_string, abort, request
import urllib.parse # For URL encoding/decoding if needed, especially for filenames

app = Flask(__name__)

# Use the current directory as the base directory to serve files from
BASE_DIR = os.path.abspath('.')

# Basic HTML template for directory listing
HTML_TEMPLATE = """
<!doctype html>
<html>
<head><title>Index of {{ display_path }}</title></head>
<body>
<h1>Index of {{ display_path }}</h1>
<ul>
    {% if parent_dir %}
    <li><a href="{{ parent_dir }}">../ (Parent Directory)</a></li>
    {% endif %}
    {% for item in items %}
    <li><a href="{{ item.url }}">{{ item.name }}{% if item.is_dir %}/{% endif %}</a></li>
    {% endfor %}
</ul>
<hr>
</body>
</html>
"""

@app.route('/')
@app.route('/<path:req_path>')
def serve_path(req_path=''):
    abs_path = os.path.join(BASE_DIR, req_path)
    norm_abs_path = os.path.normpath(abs_path) # Normalize path (e.g., remove ..)

    # Security check: Ensure the requested path is within the base directory
    if not norm_abs_path.startswith(BASE_DIR):
        print(f"Forbidden access attempt: {req_path} resolved to {norm_abs_path}")
        abort(403) # Forbidden

    # Check if path exists
    if not os.path.exists(norm_abs_path):
        print(f"Not Found: {req_path} resolved to {norm_abs_path}")
        abort(404) # Not Found

    # If it's a directory, list its contents
    if os.path.isdir(norm_abs_path):
        try:
            dir_items = os.listdir(norm_abs_path)
        except OSError as e:
            print(f"Error listing directory {norm_abs_path}: {e}")
            abort(500) # Internal Server Error

        items_list = []
        # Process directories first, then files
        for item in sorted(dir_items):
            item_abs_path = os.path.join(norm_abs_path, item)
            if os.path.isdir(item_abs_path):
                 # URL encode the item name in case it has special characters
                item_url = urllib.parse.quote(os.path.join(req_path, item))
                items_list.append({'name': item, 'url': f'/{item_url}', 'is_dir': True})

        for item in sorted(dir_items):
             item_abs_path = os.path.join(norm_abs_path, item)
             if os.path.isfile(item_abs_path):
                 # URL encode the item name
                item_url = urllib.parse.quote(os.path.join(req_path, item))
                items_list.append({'name': item, 'url': f'/{item_url}', 'is_dir': False})

        parent_dir_url = None
        if req_path: # If not the root directory
            parent_path = os.path.dirname(req_path)
            parent_dir_url = '/' + parent_path if parent_path else '/' # Go to root if parent is empty

        # Display path should be user-friendly
        display_path = '/' + req_path if req_path else '/'

        return render_template_string(
            HTML_TEMPLATE,
            display_path=display_path,
            items=items_list,
            parent_dir=parent_dir_url
        )

    # If it's a file, serve it
    elif os.path.isfile(norm_abs_path):
        try:
            # send_from_directory needs the directory and the filename relative to that directory
            # The 'req_path' already contains the relative path including subdirs
            return send_from_directory(BASE_DIR, req_path, as_attachment=False) # Set as_attachment=True to force download
        except Exception as e:
             print(f"Error sending file {norm_abs_path}: {e}")
             abort(500)
    else:
         # Should not happen if exists() and isdir() checks pass, but handle just in case
         print(f"Unknown item type: {norm_abs_path}")
         abort(500)


if __name__ == "__main__":
    # Get local IP address to display helpful message
    # (This part is optional but helpful for the user)
    host_ip = '0.0.0.0' # Default listen address
    port = 80
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) # Connect to a known external server to find local IP
        local_ip = s.getsockname()[0]
        s.close()
        print(f"[*] Serving files from: {BASE_DIR}")
        print(f"[*] Server starting...")
        print(f"[*] Access it from this computer: http://127.0.0.1:{port}")
        print(f"[*] Access it from other devices on the network: http://{local_ip}:{port}")
    except Exception:
        print(f"[*] Could not determine local IP address automatically.")
        print(f"[*] Server starting...")
        print(f"[*] Access it from this computer: http://127.0.0.1:{port}")
        print(f"[*] Access it from other devices on the network using this computer's local IP address on port {port}.")
        print(f"[*] Listening on {host_ip}:{port}")

    # Run the app, listening on all interfaces (0.0.0.0)
    app.run(host=host_ip, port=port, debug=False) # Turn debug=False for general use
    # Use debug=True for development (provides auto-reload and detailed errors)
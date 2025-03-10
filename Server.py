import os
from http.server import SimpleHTTPRequestHandler, HTTPServer

class FileServerHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # Get the full path of the requested file
        path = self.translate_path(self.path)
        
        # Check if the path is a file
        if os.path.isfile(path):
            # Set headers to force download
            self.send_response(200)
            
            # Set Content-Type to application/octet-stream for .bat files and others
            if path.endswith('.bat') or path.endswith('.exe') or path.endswith('.sh'):
                self.send_header('Content-Type', 'application/octet-stream')
            else:
                # Use the default Content-Type for other files
                self.send_header('Content-Type', self.guess_type(path))
            
            # Force download by setting Content-Disposition
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(path)}"')
            self.send_header('Content-Length', str(os.path.getsize(path)))
            self.end_headers()
            
            # Send the file content
            with open(path, 'rb') as file:
                self.wfile.write(file.read())
        else:
            # If it's not a file, list the directory contents
            super().do_GET()

    def list_directory(self, path):
        try:
            # List all files in the current directory
            files = os.listdir(path)
            files.sort(key=lambda a: a.lower())
            r = []
            displaypath = os.path.basename(self.path)
            r.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">')
            r.append('<html>\n<head>')
            r.append('<meta http-equiv="Content-Type" content="text/html; charset=utf-8">')
            r.append(f'<title>Directory listing for {displaypath}</title>\n</head>')
            r.append('<body>\n<h1>Directory, listing for {}</h1>'.format(displaypath))
            r.append('<hr>\n<ul>')
            for name in files:
                fullname = os.path.join(path, name)
                if os.path.isdir(fullname):
                    name = name + '/'
                r.append('<li><a href="{}">{}</a></li>'.format(name, name))
            r.append('</ul>\n<hr>\n</body>\n</html>\n')
            encoded = '\n'.join(r).encode('utf-8', 'surrogateescape')
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except Exception:
            self.send_error(404, "No permission to list directory")

def run(server_class=HTTPServer, handler_class=FileServerHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting httpd server on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
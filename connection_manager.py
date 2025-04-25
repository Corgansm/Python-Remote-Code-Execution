# connection_manager.py

import socket
import threading
import time
import json

class ConnectionManager:
    """
    Manages active client connections, providing registration, tracking,
    and a separate management interface.
    """
    def __init__(self, host, management_port, connection_timeout=60):
        """
        Initializes the ConnectionManager.

        Args:
            host (str): The host address for the management interface.
            management_port (int): The port for the management interface.
            connection_timeout (int): Timeout in seconds for inactive connections (optional).
        """
        self.host = host
        self.management_port = management_port
        self.connection_timeout = connection_timeout # Optional: For future inactivity cleanup

        self.connections = {}  # {client_id: {'conn': socket, 'addr': tuple, 'last_active': float}}
        self.next_client_id = 0
        self.lock = threading.Lock()
        self.running = False
        self.management_thread = None
        self.management_socket = None
        # Optional: Add a thread for periodic inactivity checks if needed
        # self.cleanup_thread = None

    def _get_next_id(self):
        """Generates the next unique client ID. Assumes lock is held."""
        self.next_client_id += 1
        return self.next_client_id

    def register_connection(self, conn, addr):
        """
        Registers a new client connection.

        Args:
            conn (socket.socket): The client socket object.
            addr (tuple): The client address (ip, port).

        Returns:
            int: The unique ID assigned to this connection.
        """
        with self.lock:
            client_id = self._get_next_id()
            self.connections[client_id] = {
                'conn': conn,
                'addr': addr,
                'last_active': time.time()
            }
            print(f"[CM] Registered connection ID {client_id} from {addr}")
            return client_id

    def unregister_connection(self, client_id):
        """
        Unregisters a client connection by its ID. Does not close the socket.

        Args:
            client_id (int): The ID of the connection to unregister.
        """
        with self.lock:
            if client_id in self.connections:
                addr = self.connections[client_id]['addr']
                # Don't close the socket here, let the caller handle it
                del self.connections[client_id]
                print(f"[CM] Unregistered connection ID {client_id} from {addr}")
            else:
                # FIX: Avoid printing if attempting to unregister during shutdown cleanup maybe?
                # Keep print for now for debugging.
                print(f"[CM] Attempted to unregister unknown connection ID {client_id}")


    def update_activity(self, client_id):
        """
        Updates the last activity timestamp for a connection.

        Args:
            client_id (int): The ID of the connection to update.
        """
        with self.lock:
            if client_id in self.connections:
                self.connections[client_id]['last_active'] = time.time()
            # else: connection might have been closed/unregistered concurrently

    def get_connection_count(self):
        """
        Returns the current number of active connections.

        Returns:
            int: The number of connections.
        """
        with self.lock:
            return len(self.connections)

    def list_connections(self):
        """
        Returns a list of details about active connections.

        Returns:
            list: A list of dictionaries, each containing 'id', 'addr', 'last_active'.
        """
        with self.lock:
            details = []
            now = time.time()
            for client_id, data in self.connections.items():
                details.append({
                    'id': client_id,
                    'addr': f"{data['addr'][0]}:{data['addr'][1]}",
                    'last_active': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data['last_active'])),
                    'idle_seconds': int(now - data['last_active'])
                })
            return details

    def get_connection_details(self, client_id):
        """Gets details for a specific connection ID."""
        with self.lock:
            if client_id in self.connections:
                data = self.connections[client_id]
                now = time.time()
                return {
                    'id': client_id,
                    'addr': f"{data['addr'][0]}:{data['addr'][1]}",
                    'last_active': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data['last_active'])),
                    'idle_seconds': int(now - data['last_active'])
                }
            return None

    def kick_connection(self, client_id):
        """
        Forcibly closes and unregisters a connection.

        Args:
            client_id (int): The ID of the connection to kick.

        Returns:
            bool: True if the connection was found and kicked, False otherwise.
        """
        conn_to_close = None
        addr = None
        with self.lock:
            if client_id in self.connections:
                # FIX: Pop the entry to prevent others from using it after removal starts
                conn_data = self.connections.pop(client_id, None)
                if conn_data:
                    conn_to_close = conn_data['conn']
                    addr = conn_data['addr']
                    print(f"[CM] Kicking connection ID {client_id} from {addr}")
                # else: # Should not happen if client_id in self.connections was true
                #    pass
            # else already checked implicitly by 'if client_id in self.connections'

        if conn_to_close:
            try:
                # FIX: Added check if conn_to_close still valid before shutdown/close
                if conn_to_close:
                    conn_to_close.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                # Ignore errors like "not connected" if socket already closed/broken
                if e.errno != 10057 and e.errno != 9: # WSAENOTCONN, EBADF
                     print(f"[CM] OSError during shutdown for kicked {client_id}: {e}")
                pass
            except Exception as e:
                 print(f"[CM] Error during shutdown for kicked {client_id}: {e}")
            finally:
                try:
                    # FIX: Added check if conn_to_close still valid before close
                    if conn_to_close:
                        conn_to_close.close()
                    print(f"[CM] Closed socket for kicked connection ID {client_id}")
                except Exception as e:
                     print(f"[CM] Error closing socket for kicked {client_id}: {e}")
            return True
        else:
            # FIX: Message unchanged, but pop() above makes this condition slightly different
            print(f"[CM] Attempted to kick unknown or already removed connection ID {client_id}")
            return False


    def _handle_management_client(self, mgmt_conn, mgmt_addr):
        """Handles a single connection to the management interface."""
        print(f"[CM Management] Connection from {mgmt_addr}")
        try:
            while self.running: # FIX: Check self.running in loop condition
                mgmt_conn.sendall(b"> ")
                command = mgmt_conn.recv(1024).decode('utf-8', errors='ignore').strip()
                if not command:
                    break # Client disconnected

                print(f"[CM Management] Received command: {command}")
                response = ""
                parts = command.lower().split()
                cmd_verb = parts[0] if parts else ""

                if cmd_verb == "list":
                    connections = self.list_connections()
                    if connections:
                         response = json.dumps(connections, indent=2) + "\n"
                    else:
                         response = "No active connections.\n"
                elif cmd_verb == "info" and len(parts) > 1:
                    try:
                        client_id = int(parts[1])
                        details = self.get_connection_details(client_id)
                        if details:
                            response = json.dumps(details, indent=2) + "\n"
                        else:
                            response = f"No connection found with ID {client_id}.\n"
                    except ValueError:
                        response = "Invalid ID format. Usage: info <id>\n"
                elif cmd_verb == "kick" and len(parts) > 1:
                     try:
                        client_id = int(parts[1])
                        if self.kick_connection(client_id):
                             response = f"Connection ID {client_id} kicked.\n"
                        else:
                             response = f"Failed to kick connection ID {client_id} (not found).\n"
                     except ValueError:
                         response = "Invalid ID format. Usage: kick <id>\n"
                elif cmd_verb == "count":
                    count = self.get_connection_count()
                    response = f"Active connections: {count}\n"
                elif cmd_verb == "help":
                     response = (
                        "Available commands:\n"
                        "  list         - Show active connections\n"
                        "  info <id>    - Show details for a specific connection ID\n"
                        "  kick <id>    - Forcibly close a connection by ID\n"
                        "  count        - Show the number of active connections\n"
                        "  help         - Show this help message\n"
                        "  exit         - Close this management connection\n"
                     )
                elif cmd_verb == "exit":
                     break
                else:
                     response = "Unknown command. Type 'help' for available commands.\n"

                mgmt_conn.sendall(response.encode('utf-8'))

        except ConnectionResetError:
            print(f"[CM Management] Client {mgmt_addr} disconnected abruptly.")
        except socket.error as e:
            # FIX: Don't log errors if manager is stopping
            if self.running:
                 print(f"[CM Management] Socket error handling client {mgmt_addr}: {e}")
        except Exception as e:
            if self.running:
                 print(f"[CM Management] Error handling client {mgmt_addr}: {e}")
        finally:
            print(f"[CM Management] Closing connection from {mgmt_addr}")
            # FIX: Added check before closing
            if mgmt_conn:
                try:
                    mgmt_conn.close()
                except Exception:
                    pass # Ignore errors on close

    def _management_loop(self):
        """The main loop for the management interface server."""
        listener_socket = None # Use local variable within the loop's scope
        try:
            listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener_socket.bind((self.host, self.management_port))
            listener_socket.listen(1) # Only allow one management connection at a time
            self.management_socket = listener_socket # Assign to instance variable AFTER successful bind/listen
            print(f"[CM] Management interface listening on {self.host}:{self.management_port}")

            while self.running:
                # FIX: Check self.management_socket validity inside loop
                if not self.running or not self.management_socket:
                    break # Exit if stopped or socket closed externally
                self.management_socket.settimeout(1.0) # Timeout to check self.running
                try:
                    mgmt_conn, mgmt_addr = self.management_socket.accept()
                    # Handle management connection synchronously for simplicity,
                    # or spawn a thread if multiple mgmt clients are needed.
                    self._handle_management_client(mgmt_conn, mgmt_addr)
                except socket.timeout:
                    continue # No connection attempt, check self.running again
                except OSError as e:
                    # FIX: Check if the error is due to the socket being closed during shutdown
                    if self.running and e.errno != 10038: # WinError 10038: An operation was attempted on something that is not a socket
                         print(f"[CM Management] Error accepting connection: {e}")
                    elif not self.running:
                         # Socket likely closed intentionally during stop(), suppress error
                         break # Exit loop if not running
                    # else: # Running and Error 10038, likely socket closed by stop() - break loop
                    #    break
                except Exception as e:
                    if self.running: # Avoid logging errors during shutdown
                        print(f"[CM Management] Error accepting connection: {e}")

        except Exception as e:
             # FIX: Check if error is due to binding before printing failure message
             # Ensure self.running check happens before accessing socket potentially
             if self.running and listener_socket is None : # Error likely during setup
                 print(f"[CM Management] Failed to start management interface: {e}")
             elif self.running: # Error happened after setup
                  print(f"[CM Management] Management loop error: {e}")
        finally:
            # FIX: Close the listener_socket if it was created, ensure instance variable is cleared
            print("[CM] Management interface loop ending.")
            temp_sock = self.management_socket # Use potentially valid instance variable first
            self.management_socket = None # Clear instance variable
            if temp_sock:
                try:
                    temp_sock.close()
                except Exception:
                    pass
            elif listener_socket: # Fallback to local variable if instance one was already None/failed
                 try:
                      listener_socket.close()
                 except Exception:
                      pass
            print("[CM] Management interface stopped.")

    def start(self):
        """Starts the connection manager's background tasks (management interface)."""
        if self.running:
            print("[CM] Manager already running.")
            return

        self.running = True
        self.management_thread = threading.Thread(target=self._management_loop, daemon=True)
        self.management_thread.start()
        # Optional: Start cleanup thread here if implementing inactivity checks

    def stop(self):
        """Stops the connection manager and cleans up resources."""
        if not self.running:
            print("[CM] Manager not running.")
            return

        print("[CM] Stopping Connection Manager...")
        was_running = self.running
        self.running = False # Signal threads to stop FIRST

        # Stop management interface
        # FIX: Try closing the socket more carefully to unblock accept()
        temp_socket = self.management_socket # Grab current socket
        self.management_socket = None # Prevent reuse after closing starts

        if temp_socket:
            print("[CM] Closing management listener socket...")
            try:
                # Attempt to unblock accept() by connecting to it (may fail)
                socket.create_connection((self.host, self.management_port), timeout=0.1).close()
            except Exception:
                pass # Ignore if it fails (socket might already be closing/closed)
            try:
                temp_socket.close()
                print("[CM] Management listener socket closed.")
            except Exception as e:
                 print(f"[CM] Error during management socket close: {e}") # Informational

        if self.management_thread and self.management_thread.is_alive():
            print("[CM] Joining management thread...")
            self.management_thread.join(timeout=2.0) # Wait for thread to finish
            if self.management_thread.is_alive():
                print("[CM] Warning: Management thread did not join cleanly.")
            else:
                print("[CM] Management thread joined.")
        self.management_thread = None

        # Close all managed client connections
        print("[CM] Closing all managed client connections...")
        with self.lock:
            client_ids = list(self.connections.keys()) # Get IDs before iterating
            print(f"[CM] Found {len(client_ids)} connections to close.")
            for client_id in client_ids:
                # FIX: More robust closing within the loop
                conn_data = self.connections.pop(client_id, None) # Remove and get data atomically
                if conn_data:
                    conn = conn_data['conn']
                    addr = conn_data['addr']
                    print(f"[CM] Closing connection ID {client_id} from {addr}")
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except OSError as e:
                        # Ignore specific errors indicating socket already closed/not connected
                        if e.errno not in (10057, 10038, 9, 10022): # WSAENOTCONN, WSAENOTSOCK, EBADF, WSAEINVAL
                            print(f"[CM] OSError during shutdown for {client_id}: {e}")
                    except Exception as e:
                        print(f"[CM] Error shutting down socket {client_id}: {e}")
                    finally:
                        try:
                            conn.close()
                        except Exception as e:
                             print(f"[CM] Error closing socket {client_id}: {e}")
            # self.connections dictionary should be empty now after pop
            if self.connections:
                 print(f"[CM] Warning: {len(self.connections)} connections remained after cleanup loop.")
                 self.connections.clear()


        # Optional: Stop cleanup thread if implemented
        # if self.cleanup_thread and self.cleanup_thread.is_alive():
        #    self.cleanup_thread.join()

        print("[CM] Connection Manager stopped.")
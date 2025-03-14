# Python-RCE-Project

This project is a Python-based Remote Code Execution (RCE) tool designed for educational and research purposes. It allows for remote command execution, file upload/download, and interaction with specific processes (e.g., Minecraft) on a target machine. The tool uses a socket-based connection to communicate with an attacker's server, enabling remote control over the target system.

## Features

- **Remote Command Execution**: Execute shell commands on the target machine.
- **File Upload/Download**: Upload files to the target or download files from a specified URL.
- **Process Interaction**: Send keystrokes to specific processes (e.g., pidtxt) by PID.
- **Directory Management**: Change directories and manage files on the target system.
- **Stealth Mode**: Hide the command prompt window on Windows systems.
- **Obfuscation**: Target IP and port are base64 encoded for basic obfuscation.
- **Process Termination**: Terminate specific processes (e.g., Java) remotely.
- **Screen Share**: Share the Victim's screen to the attacker's screen.

## Usage

1. **Set Up the Attacker's Server**: 
   - Ensure the attacker's server is running and listening on the specified IP and port.
   - The target IP and port are base64 encoded in the script. Modify `encoded_target` and `encoded_port` to point to your server.

2. **Run the Script on the Target Machine**:
   - Execute the script on the target machine. It will attempt to connect to the attacker's server.

3. **Execute Commands**:
   - Once connected, you can send commands to the target machine via the socket connection.
   - Supported commands include:
     - `cd <directory>`: Change the current working directory.
     - `upload <filename>`: Upload a file to the target machine.
     - `download <filename>`: Download a file from a specified URL.
     - `pidtxt <command>`: Send keystrokes to a process (requires PID.txt file and only really works on minecraft server console processes).
     - `kill`: Terminate specific processes (e.g., Java).

4. **File Management**:
   - Files can be uploaded or downloaded between the attacker and target machine.
   - The `downloads2` command creates a directory named `Downloads2` in the user's profile for file storage.

## Important Notes

- **Educational Use Only**: This tool is intended for educational and research purposes only. Do not use it for malicious activities.
- **Legal Compliance**: Ensure you have proper authorization before using this tool on any system.
- **Security Risks**: Running this tool on a system can expose it to significant security risks. Use with caution.

## Dependencies

- Python 3.x
- `pywin32` (for Windows-specific functionality)
- `ctypes` (for handling Windows API calls)
- `requests` (for file downloads)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Corgansm/Python-RCE-Project.git

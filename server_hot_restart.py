import subprocess
import threading
import keyboard
import os
import signal

# Command to run your server
server_cmd = ["python", "production_app.py"]

# Global variable to hold the current server process
server_proc = None

def start_server():
    global server_proc
    server_proc = subprocess.Popen(server_cmd)
    server_proc.wait()  # Wait until server exits

def monitor_keys():
    global server_proc
    while True:
        keyboard.wait('r')  # Wait until 'r' is pressed
        print("\nRestarting server...")
        if server_proc:
            # Terminate the current server
            if os.name == 'nt':
                server_proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                server_proc.terminate()
            server_proc.wait()
        # Start a new server instance
        threading.Thread(target=start_server, daemon=True).start()

# Start the server in a separate thread
threading.Thread(target=start_server, daemon=True).start()
print("Press 'r' at any time to restart the server.")

# Start monitoring keys (blocking)
monitor_keys()

"""Single-instance control.

The running app listens on a local port and records it in the data folder. Starting the app again
(or `python winclipman.py --show`) finds that port, asks the running copy to open its window, and exits.
That keeps two copies from fighting over the hotkey, and it gives Wayland users, who can't have a global
hotkey, a command to bind to a desktop shortcut.
"""
import os
import socket
import threading

COMMANDS = ("show", "settings")  # the only things another process may ask for


def _port_file(data_dir):
    return os.path.join(data_dir, "instance.port")


def send(data_dir, command, timeout=0.5):
    """Ask a running instance to do `command`. Returns True if one answered."""
    try:
        with open(_port_file(data_dir), encoding="utf-8") as f:
            port = int(f.read().strip())
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as conn:
            conn.sendall(f"{command}\n".encode())
            return conn.recv(16).startswith(b"ok")
    except (OSError, ValueError):  # no file, stale port, or something else is listening there
        return False


class Server:
    def __init__(self, data_dir, on_command):
        self.data_dir, self.on_command = data_dir, on_command
        self.sock = None

    def start(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))  # loopback only
        self.sock.listen(4)
        os.makedirs(self.data_dir, exist_ok=True)
        with open(_port_file(self.data_dir), "w", encoding="utf-8") as f:
            f.write(str(self.sock.getsockname()[1]))
        threading.Thread(target=self._serve, daemon=True).start()

    def stop(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        try:
            os.remove(_port_file(self.data_dir))
        except OSError:
            pass

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except (OSError, AttributeError):  # the socket was closed by stop()
                return
            with conn:
                try:
                    conn.settimeout(1)
                    command = conn.recv(64).decode("utf-8", "replace").strip()
                    if command in COMMANDS:
                        self.on_command(command)
                        conn.sendall(b"ok\n")
                    else:
                        conn.sendall(b"no\n")
                except OSError:
                    pass

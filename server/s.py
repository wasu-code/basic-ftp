import os
import socket
import threading
import time
from pathlib import Path
from tinydb import TinyDB, Query
import bcrypt
import configparser

# Configurable Settings via Config File
CONFIG_FILE = "ftpserver.conf"
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

FTP_PORT = int(config["SERVER"]["Port"])
PASSIVE_PORT_RANGE = tuple(map(int, config["SERVER"]["PassivePortRange"].split(",")))
SESSION_TIMEOUT = int(config["SERVER"]["SessionTimeout"])
LOGIN_TIMEOUT = int(config["SERVER"]["LoginTimeout"])
DATA_TIMEOUT = int(config["SERVER"]["DataTimeout"])
ROOT_DIR = Path(config["SERVER"]["RootDirectory"]).resolve()
ALLOW_ANONYMOUS = config.getboolean("SERVER", "AllowAnonymous")

db = TinyDB("users.json")

# Preload Default Users
if not db.contains(Query().username == "anonymous"):
    db.insert(
        {"username": "anonymous", "password": None, "home": str(ROOT_DIR / "anonymous")}
    )

# xx remove it (this is only for testing)
if not db.contains(Query().username == "tst"):
    db.insert(
        {
            "username": "tst",
            "password": bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
            "home": str(ROOT_DIR / "user1"),
        }
    )


class FTPSession(threading.Thread):
    def __init__(self, client_socket, address):
        super().__init__()
        self.client_socket = client_socket
        self.address = address
        self.logged_in = False
        self.user = None
        self.cwd = None
        self.data_socket = None
        self.passive_port = None
        self.passive_socket = None
        self.start_time = time.time()
        self.last_activity = time.time()

    def send(self, message):
        self.client_socket.sendall(f"{message}\r\n".encode("utf-8"))

    def receive(self):
        data = self.client_socket.recv(1024).decode("utf-8").strip()
        self.last_activity = time.time()
        return data

    def login(self, username, password=None):
        user = db.get(Query().username == username)
        if user and (
            user["password"] is None
            or bcrypt.checkpw(password.encode(), user["password"].encode())
        ):
            self.logged_in = True
            self.user = username
            self.cwd = Path(user["home"]).resolve()
            self.cwd.mkdir(parents=True, exist_ok=True)
            return True
        return False

    def sanitize_path(self, path):
        if not self.cwd:
            raise PermissionError("User not logged in.")
        resolved_path = (self.cwd / path).resolve()
        if not str(resolved_path).startswith(str(self.cwd)):
            raise PermissionError("Access outside home directory is forbidden.")
        return resolved_path

    def handle_passive_mode(self):
        self.passive_port = PASSIVE_PORT_RANGE[0]
        while True:
            try:
                self.passive_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.passive_socket.bind(("", self.passive_port))
                self.passive_socket.listen(1)
                break
            except OSError:
                self.passive_port += 1
                if self.passive_port > PASSIVE_PORT_RANGE[1]:
                    self.send("425 Can't open passive connection.")
                    return
        ip = self.address[0].replace(".", ",")
        p1 = self.passive_port // 256
        p2 = self.passive_port % 256
        self.send(f"227 Entering Passive Mode ({ip},{p1},{p2}).")
        self.data_socket, _ = self.passive_socket.accept()

    def handle_client(self):
        self.send("220 Welcome to UŚ FTP Server")
        try:
            login_timeout = time.time() + LOGIN_TIMEOUT
            while not self.logged_in:
                if time.time() > login_timeout:
                    self.send("421 Login timeout, closing connection.")
                    self.client_socket.close()
                    return
                data = self.receive()
                cmd, *args = data.split()
                if cmd.upper() == "USER":
                    self.send("331 Username received, need password.")
                    username = args[0]
                elif cmd.upper() == "PASS":
                    password = args[0] if args else None
                    if self.login(username, password):
                        self.send("230 User logged in, proceed.")
                    else:
                        self.send("530 Login incorrect.")
                else:
                    self.send("530 Please login with USER and PASS.")

            while True:
                if time.time() - self.last_activity > SESSION_TIMEOUT:
                    self.send("421 Session timeout, closing connection.")
                    self.client_socket.close()
                    return
                data = self.receive()
                if not data:
                    break
                cmd, *args = data.split()
                if cmd.upper() == "PASV":
                    self.handle_passive_mode()
                elif cmd.upper() == "LIST":
                    if not self.data_socket:
                        self.send("425 Use PASV first.")
                    else:
                        self.send("150 Here comes the directory listing.")
                        files = "\r\n".join(os.listdir(self.cwd))
                        self.data_socket.sendall(files.encode("utf-8"))
                        self.data_socket.close()
                        self.data_socket = None
                        self.send("226 Directory send ok.")
                elif cmd.upper() == "PWD":
                    self.send(f'257 "{self.cwd}" is the current directory.')
                elif cmd.upper() == "QUIT":
                    self.send("221 Goodbye.")
                    self.client_socket.close()
                    break
                elif cmd.upper() in ["TYPE", "MODE", "STRU"]:
                    # TODO
                    if cmd.upper() == "TYPE" and args and args[0].upper() == "I":
                        self.send("200 Type set to I (binary).")
                    elif cmd.upper() == "MODE" and args and args[0].upper() == "S":
                        self.send("200 Mode set to S (stream).")
                    elif cmd.upper() == "STRU" and args and args[0].upper() == "F":
                        self.send("200 Structure set to F (file).")
                    else:
                        self.send("504 Command not implemented for parameter.")
                else:
                    self.send("502 Command not implemented.")
        except Exception as e:
            self.send(f"500 Internal server error: {e}")
            self.client_socket.close()

    def run(self):
        self.handle_client()


class FTPServer:
    def __init__(self, host="0.0.0.0", port=FTP_PORT):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.sessions = []

    def start(self):
        print(f"FTP Server running on port {FTP_PORT}")
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                session = FTPSession(client_socket, address)
                session.start()
                self.sessions.append(session)
        except KeyboardInterrupt:
            print("Shutting down FTP server.")
            self.server_socket.close()


if __name__ == "__main__":
    server = FTPServer()
    server.start()

import os
import socket
import threading
from pathlib import Path
from tinydb import TinyDB, Query
import bcrypt
import configparser
import sys

"""
Do konfiguracji używane są dwa pliki 
- <nazwa>.conf (nazwa do konfiguracji niżej, domyślnie ftpserver.conf)
- users.json (opcjonalne, zostanie utworzony automatycznie jeśli nie podany)
"""

# Configurable Settings via Config File
CONFIG_FILE = "ftpserver.conf"
config = configparser.ConfigParser()
try:
    config.read(CONFIG_FILE)
    FTP_IP = config["SERVER"].get("Host", "0.0.0.0")
    FTP_PORT = int(config["SERVER"].get("Port", "21"))
    PASSIVE_PORT_RANGE = tuple(
        map(int, config["SERVER"].get("PassivePortRange", "50000,50100").split(","))
    )
    SESSION_TIMEOUT = int(config["SERVER"].get("SessionTimeout", "300"))
    LOGIN_TIMEOUT = int(config["SERVER"].get("LoginTimeout", "30"))
    DATA_TIMEOUT = int(config["SERVER"].get("DataTimeout", "60"))
    ROOT_DIR = Path(config["SERVER"].get("RootDirectory")).resolve()
    ALLOW_ANONYMOUS = config["SERVER"].getboolean("AllowAnonymous", False)
except configparser.NoSectionError as e:
    print(f"Error: Missing section in configuration file: {e}", file=sys.stderr)
    sys.exit(1)
except configparser.NoOptionError as e:
    print(f"Error: Missing option in configuration file: {e}", file=sys.stderr)
    sys.exit(1)
except ValueError as e:
    print(f"Error: Invalid value in configuration file: {e}", file=sys.stderr)
    sys.exit(1)
except FileNotFoundError as e:
    print(f"Error: Configuration file not found: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)


db = TinyDB("users.json")

# Preload Default Users
if not db.contains(Query().username == "anonymous"):
    db.insert(
        {"username": "anonymous", "password": None, "home": str(ROOT_DIR / "anonymous")}
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
        # self.start_time = time.time()
        # self.last_activity = time.time()

    def send(self, message):
        self.client_socket.sendall(f"{message}\r\n".encode("utf-8"))
        print(f"Sent: {message}")

    def receive(self):
        try:
            data = self.client_socket.recv(1024).decode("utf-8").strip()
            # self.last_activity = time.time()
            print(f"Received: {data}")
            return data
        except Exception as e:
            print(f"Error: {e}")
            return None

    def login(self, username, password=None):
        user = db.get(Query().username == username)
        if user and (
            user["password"] is None
            or (
                password
                and bcrypt.checkpw(password.encode(), user["password"].encode())
            )
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
        # Inform the client of the passive mode
        ip = self.address[0].replace(".", ",")
        p1 = self.passive_port // 256
        p2 = self.passive_port % 256
        self.send(f"227 Entering Passive Mode ({ip},{p1},{p2}).")

        try:
            self.passive_socket.settimeout(DATA_TIMEOUT)
            self.data_socket, _ = self.passive_socket.accept()
        except socket.timeout:
            # Handle the timeout
            print(
                f"Timeout: No connection to data socket was made within {DATA_TIMEOUT}. Closing data connection"
            )
            self.send("425 Data connection timed out.")
            self.passive_socket.close()  # Close the passive socket
            return
        finally:
            # Close the passive socket after accepting the connection
            self.passive_socket.close()

    def handle_client(self):
        self.send("220 Welcome to UŚ FTP Server")
        self.client_socket.settimeout(LOGIN_TIMEOUT)
        try:
            # login_timeout = time.time() + LOGIN_TIMEOUT
            while not self.logged_in:
                # if time.time() > login_timeout:
                #     self.send("421 Login timeout, closing connection.")
                #     self.client_socket.close()
                #     return
                data = self.receive()
                if not data:
                    print("closing client socket")
                    self.client_socket.close()
                    return
                cmd, *args = data.split()
                if cmd.upper() == "USER":
                    self.send("331 Username received, need password.")
                    username = args[0]
                elif cmd.upper() == "PASS":
                    password = args[0] if args else None
                    if self.login(username, password):
                        self.send("230 User logged in, proceed.")
                        self.client_socket.settimeout(SESSION_TIMEOUT)
                    else:
                        self.send("530 Credentials incorrect.")
                else:
                    self.send("530 Please login with USER and PASS.")

            while True:
                """handle commands"""
                # if time.time() - self.last_activity > SESSION_TIMEOUT:
                #     self.send("421 Session timeout, closing connection.")
                #     self.client_socket.close()
                #     return
                data = self.receive()
                if not data:
                    break
                cmd, *args = data.split()

                match cmd.upper():
                    case "PASV":
                        self.handle_passive_mode()

                    case "LIST":
                        if not self.data_socket:
                            self.send("425 Use PASV first.")
                        else:
                            self.send("150 Here comes the directory listing.")
                            files = "\r\n".join(os.listdir(self.cwd))
                            self.data_socket.sendall(files.encode("utf-8"))
                            self.data_socket.close()
                            self.data_socket = None
                            self.send("226 Directory send ok.")

                    case "PWD":
                        # TODO don't expose full path; ftp root directory as start of absolute path
                        self.send(f'257 "{self.cwd}" is the current directory.')

                    case "TYPE" | "MODE" | "STRU":
                        # Handle TYPE, MODE, STRU with arguments
                        # TODO
                        if cmd.upper() == "TYPE" and args and args[0].upper() == "I":
                            self.send("200 Type set to I (binary).")
                        elif cmd.upper() == "MODE" and args and args[0].upper() == "S":
                            self.send("200 Mode set to S (stream).")
                        elif cmd.upper() == "STRU" and args and args[0].upper() == "F":
                            self.send("200 Structure set to F (file).")
                        else:
                            self.send("504 Command not implemented for parameter.")

                    case "NOP":
                        # No Operation
                        self.send("200 Command okay.")

                    case "QUIT":
                        self.send("221 Goodbye.")
                        self.client_socket.close()
                        break

                    case _:
                        self.send("502 Command not implemented.")
        except socket.timeout:
            self.send("421 Session timeout, closing connection.")
            self.client_socket.close()
        except Exception as e:
            self.send(f"500 Internal server error")
            print(f"Error: {e}")
            self.client_socket.close()

    def run(self):
        self.handle_client()


class FTPServer:
    def __init__(self, host="0.0.0.0", port=FTP_PORT):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            self.sessions = []
        except OSError as e:
            if e.errno == 10048:
                print(
                    f"Error: Port {FTP_PORT} for ip {FTP_IP} is in use. Change target port in configuration file {CONFIG_FILE}."
                )
            else:
                print(f"Unexpected error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)

    def start(self):
        print(f"FTP Server running on port {FTP_PORT}")
        try:
            self.server_socket.settimeout(
                1.0
            )  # Set a timeout to allow checking for interrupt
            while True:
                try:
                    client_socket, address = self.server_socket.accept()
                except socket.timeout:
                    continue  # Allows the loop to periodically check for KeyboardInterrupt
                session = FTPSession(client_socket, address)
                session.start()
                self.sessions.append(session)
        except KeyboardInterrupt:
            print("Shutting down FTP server.")
            self.server_socket.close()


if __name__ == "__main__":
    server = FTPServer(host=FTP_IP)
    server.start()

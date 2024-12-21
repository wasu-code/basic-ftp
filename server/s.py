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
    print(f"Error: Missing section in configuration file: {e}")
    sys.exit(1)
except configparser.NoOptionError as e:
    print(f"Error: Missing option in configuration file: {e}")
    sys.exit(1)
except ValueError as e:
    print(f"Error: Invalid value in configuration file: {e}")
    sys.exit(1)
except FileNotFoundError as e:
    print(f"Error: Configuration file not found: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)


db = TinyDB("users.json")

# Preload Default Users
if not db.contains(Query().username == "anonymous"):
    db.insert(
        {"username": "anonymous", "password": None, "home": str(ROOT_DIR / "anonymous")}
    )


class FTPSession(threading.Thread):

    def __init__(self, client_socket, address, ftp_server):
        super().__init__()
        self.client_socket = client_socket
        self.address = address
        self.logged_in = False
        self.user = None
        self.cwd = None
        self.home = None
        self.data_socket = None
        self.passive_port = None
        self.passive_socket = None
        self.ftp_server = ftp_server
        self.transfer_type = "I"

    def send(self, message):
        self.client_socket.sendall(f"{message}\r\n".encode("utf-8"))
        print(f"Sent: {message}")

    def receive(self):
        data = self.client_socket.recv(1024).decode("utf-8").strip()
        print(f"Received: {data}")
        return data

    def login(self, username, password=None):
        user = db.get(Query().username == username)
        if user and (
            (  # password for this user is not required and anonymous access is allowed
                user["password"] is None and ALLOW_ANONYMOUS is True
            )
            or (  # password for this user is required and matches the provided
                password
                and user["password"]
                and bcrypt.checkpw(password.encode(), user["password"].encode())
            )
        ):
            self.logged_in = True
            self.user = username
            user_home = Path(user["home"]).resolve()
            self.cwd = user_home
            self.home = user_home
            self.cwd.mkdir(parents=True, exist_ok=True)
            return True
        return False

    def sanitize_path(self, path, check_full_path=True):
        """
        Return the absolute path if it is within the user's home directory.

        Parameters:
            path (str): The path to sanitize.
            check_full_path (bool): If True, check the existence of the full path.
                                    If False, skip the existence check for the last fragment.
        """
        if not self.cwd:
            raise PermissionError("User not logged in.")

        if path.startswith("/"):  # client uses absolute path
            resolved_path = (self.home / path.lstrip("/")).resolve()
        else:  # client uses relative path
            resolved_path = (self.cwd / path).resolve()

        if not str(resolved_path).startswith(str(self.home)):
            raise PermissionError("Access outside home directory is forbidden.")

        if check_full_path:
            if not resolved_path.exists():
                raise PermissionError("File or directory does not exist.")
        else:
            # Check all parts of the path except the last fragment
            parent_path = resolved_path.parent
            if not parent_path.exists():
                raise PermissionError("Parent directory does not exist.")

        print(
            f"resolved_path: {resolved_path}\n cwd: {self.cwd}\n path: {path}\n home: {self.home}"
        )
        return resolved_path

    def ftp_path(self, path):
        """Return the path relative to the user's home directory using forward slashes"""
        relative_path = path.relative_to(self.home)
        return "/" + str(relative_path).replace("\\", "/")

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
        self.client_socket.settimeout(LOGIN_TIMEOUT)  # Set a timeout for login
        try:
            while not self.logged_in:
                """login process"""
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
                        self.client_socket.settimeout(
                            SESSION_TIMEOUT
                        )  # User logged in, set a timeout for session
                    else:
                        self.send("530 Credentials incorrect.")
                else:
                    self.send("530 Please login with USER and PASS.")

            while True:
                """handle commands"""
                if self.client_socket.fileno() == -1:
                    break  # connection is closed
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
                            # files = "\r\n".join(os.listdir(self.cwd))
                            # self.data_socket.sendall(files.encode("utf-8"))
                            # self.data_socket.close()
                            # self.data_socket = None
                            # self.send("226 Directory send ok.")
                            entries = os.listdir(self.cwd)
                            response = []
                            for entry in entries:
                                entry_path = self.cwd / entry
                                if entry_path.is_dir():
                                    response.append(
                                        f"drwxr-xr-x 2 user group 4096 Jan 1 00:00 {entry}"
                                    )
                                else:
                                    size = entry_path.stat().st_size
                                    response.append(
                                        f"-rw-r--r-- 1 user group {size} Jan 1 00:00 {entry}"
                                    )
                            self.data_socket.sendall(
                                "\r\n".join(response).encode("utf-8")
                            )
                            self.data_socket.close()
                            self.data_socket = None
                            self.send("226 Directory send ok.")

                    case "PWD":
                        self.send(
                            f'257 "{self.ftp_path(self.cwd)}" is the current directory.'
                        )

                    case "CWD":
                        if not args:
                            self.send("501 No directory specified.")
                        else:
                            try:
                                path = self.sanitize_path(args[0])
                                self.cwd = path
                                self.send(
                                    f'250 CWD command successful. "{self.ftp_path(self.cwd)}" is current directory.'
                                )
                            except PermissionError:
                                self.send("550 Permission denied.")

                    case "CDUP":
                        try:
                            self.cwd = self.sanitize_path("..")
                            self.send(
                                f'250 CDUP command successful. "{self.ftp_path(self.cwd)}" is current directory.'
                            )
                        except PermissionError:
                            self.send("550 Permission denied.")

                    case "MKD":
                        if not args:
                            self.send("501 No directory specified.")
                        else:
                            try:
                                path = self.sanitize_path(
                                    args[0], check_full_path=False
                                )
                                path.mkdir(parents=True, exist_ok=True)
                                self.send(f"257 Directory created: {args[0]}.")
                            except PermissionError:
                                self.send("550 Permission denied.")

                    case "RMD":
                        if not args:
                            self.send("501 No directory specified.")
                        else:
                            try:
                                path = self.sanitize_path(args[0])
                                path.rmdir()
                                self.send(f"250 Directory deleted: {args[0]}.")
                            except PermissionError:
                                self.send("550 Permission denied.")

                    case "TYPE" | "MODE" | "STRU":
                        # Handle TYPE, MODE, STRU with arguments
                        if args and args[0].upper() == "I":
                            self.transfer_type = "I"
                            self.send("200 Type set to I (binary).")
                        elif args and args[0].upper() == "A":
                            self.transfer_type = "A"
                            self.send("200 Type set to A (ASCII).")
                        elif cmd.upper() == "MODE" and args and args[0].upper() == "S":
                            self.send("200 Mode set to S (stream).")
                        elif cmd.upper() == "STRU" and args and args[0].upper() == "F":
                            self.send("200 Structure set to F (file).")
                        else:
                            self.send("504 Command not implemented for parameter.")

                    case "STOR":
                        if not self.data_socket:
                            self.send("425 Use PASV first.")
                        else:
                            filename = args[0]
                            try:
                                path = self.sanitize_path(
                                    filename, check_full_path=False
                                )
                            except PermissionError as e:
                                self.send("550 Permission denied.")
                                print(f"Error: {e}")
                                self.data_socket.close()
                                self.data_socket = None
                                continue
                            self.send("150 Ok to send data.")
                            mode = "wb" if self.transfer_type == "I" else "w"
                            with open(path, mode) as f:
                                while True:
                                    data = self.data_socket.recv(1024)
                                    if not data:
                                        break
                                    if self.transfer_type == "A":
                                        data = data.decode("utf-8")
                                    f.write(data)
                            self.data_socket.close()
                            self.data_socket = None
                            self.send("226 Transfer complete.")

                    case "RETR":
                        if not self.data_socket:
                            self.send("425 Use PASV first.")
                        else:
                            filename = args[0]
                            try:
                                path = self.sanitize_path(filename)
                            except PermissionError as e:
                                self.send("550 Permission denied.")
                                print(f"Error: {e}")
                                self.data_socket.close()
                                self.data_socket = None
                                continue
                            self.send("150 Will send data.")
                            mode = "rb" if self.transfer_type == "I" else "r"
                            with open(path, mode) as f:
                                while True:
                                    data = f.read(1024)
                                    if not data:
                                        break
                                    if self.transfer_type == "A":
                                        data = data.encode("utf-8")
                                    self.data_socket.sendall(data)
                            self.data_socket.close()
                            self.data_socket = None
                            self.send("226 Transfer complete.")

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
        return self.ftp_server.remove_session(self)


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

    def remove_session(self, session):
        # Remove the session from the sessions list
        if session in self.sessions:
            self.sessions.remove(session)
            print(f"Session removed. Active sessions: {len(self.sessions)}")

    def start(self):
        print(f"FTP Server running on port {FTP_PORT}")
        try:
            self.server_socket.settimeout(
                1.0
            )  # Set a timeout to allow checking for interrupt
            while True:
                print(
                    f"Awaiting new connections. {len(self.sessions)} active connections"
                )
                try:
                    client_socket, address = self.server_socket.accept()
                except socket.timeout:
                    continue  # Allows the loop to periodically check for KeyboardInterrupt
                print("Wild connection appeared!")
                session = FTPSession(client_socket, address, ftp_server=self)
                session.start()
                self.sessions.append(session)
        except KeyboardInterrupt:
            print("Shutting down FTP server.")
            self.server_socket.close()


if __name__ == "__main__":
    server = FTPServer(host=FTP_IP)
    server.start()

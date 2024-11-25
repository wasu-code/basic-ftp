import socket
import sys
from urllib.parse import urlparse
import os


class FTPClient:
    def __init__(self, host, port=21, username="anonymous", password=""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.control_socket = None

    def connect(self):
        print(f"Connecting to {self.host}:{self.port}")
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket.connect((self.host, self.port))
        print(self._get_response())  # Welcome message

    def login(self):
        self._send_command(f"USER {self.username}")
        print(self._get_response())
        self._send_command(f"PASS {self.password}")
        print(self._get_response())

    def _send_command(self, command):
        print(f">> Sending command: {command}")
        self.control_socket.sendall((command + "\r\n").encode("utf-8"))

    def _get_response(self):
        response = self.control_socket.recv(1024).decode("utf-8")
        return "<< " + response

    def close(self):
        self._send_command("QUIT")
        print(self._get_response())
        self.control_socket.close()

    def list_directory(self, path=""):
        data_socket = self._open_data_connection()
        self._send_command(f"LIST {path}")
        print(self._get_response())
        self._print_data_response(data_socket)

    def make_directory(self, path):
        self._send_command(f"MKD {path}")
        print(self._get_response())

    def remove_directory(self, path):
        self._send_command(f"RMD {path}")
        print(self._get_response())

    def delete_file(self, path):
        self._send_command(f"DELE {path}")
        print(self._get_response())

    def upload_file(self, local_path, remote_path):
        with open(local_path, "rb") as f:
            data_socket = self._open_data_connection()
            self._send_command(f"STOR {remote_path}")
            print(self._get_response())
            data_socket.sendall(f.read())
            data_socket.close()
            response = self._get_response()
            print(response)
            response_code = response.split(" ", 1)[1]
            return True if response_code // 100 == 2 else False

    def download_file(self, remote_path, local_path):
        data_socket = self._open_data_connection()
        self._send_command(f"RETR {remote_path}")
        print(self._get_response())
        with open(local_path, "wb") as f:
            while True:
                data = data_socket.recv(1024)
                if not data:
                    break
                f.write(data)
        data_socket.close()
        print(self._get_response())

    def _open_data_connection(self):
        self._send_command("PASV")
        response = self._get_response()
        print(response)

        start = response.find("(") + 1
        end = response.find(")")
        numbers = list(map(int, response[start:end].split(",")))
        ip_address = ".".join(map(str, numbers[:4]))
        port = (numbers[4] << 8) + numbers[5]

        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.connect((ip_address, port))
        return data_socket

    def _print_data_response(self, data_socket):
        """
        Reads and prints the response from the data socket in a human-readable format.
        """
        try:
            while True:
                data = data_socket.recv(1024).decode("utf-8")
                if not data:
                    break
                print(data, end="")
        except Exception as e:
            print(f"Error reading data response: {e}")
        finally:
            print("\n")
            data_socket.close()


def parse_command_line():
    if len(sys.argv) < 3:
        print("Usage: usftp [operation] [param1] [param2]")
        sys.exit(1)

    operation = sys.argv[1]
    param1 = sys.argv[2] if len(sys.argv) > 2 else None
    param2 = sys.argv[3] if len(sys.argv) > 3 else None
    return operation, param1, param2


def main():
    operation, param1, param2 = parse_command_line()

    if param1.startswith("ftp://"):
        parsed_url = urlparse(param1)
        host = parsed_url.hostname
        port = parsed_url.port or 21
        username = parsed_url.username or "anonymous"
        password = parsed_url.password or ""
        path = parsed_url.path or "/"
    else:
        print("Invalid FTP URL.")
        sys.exit(1)

    client = FTPClient(host, port, username, password)

    try:
        client.connect()
        client.login()

        def full_path():
            """
            joins path from url (target remote folder) and param2 (relative path and folder name to create) to get full path
            """
            return os.path.normpath(os.path.join(path, param2 or "")).replace("\\", "/")

        match operation:
            case "ls":
                client.list_directory(parsed_url.path)
            case "mkdir":
                client.make_directory(full_path())
            case "rmdir":
                client.remove_directory(full_path())
            case "rm":
                client.delete_file(full_path())
            case "cp":
                if param1.startswith("ftp://"):
                    client.download_file(param1, param2)
                else:
                    client.upload_file(param1, param2)
            case "mv":
                # TODO direction? s->local, local->s
                if param1.startswith("ftp://"):
                    success = client.upload_file(param1, param2)
                    if success:
                        client.delete_file(param1)
                    else:
                        print("Upload failed, nothing deleted.")
                else:
                    # download file
                    # client.download_file(param1, param2)
                    # check if success
                    # remove from server
                    # client.delete_file(full_path())
                    pass
            case _:
                print("Unknown operation.")
    finally:
        client.close()


if __name__ == "__main__":
    main()

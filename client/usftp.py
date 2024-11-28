import socket
import sys
from urllib.parse import urlparse
import os
import ipaddress

# https://datatracker.ietf.org/doc/html/rfc959 (page 40) 4.2.2 Numeric  Order List of Reply Codes


class ExtendedResponse(str):
    def __new__(cls, value: str, code: int = None, ok: bool = None):
        # Create the response (string) part
        instance = super().__new__(cls, value)
        # Add additional attributes
        instance.code = code
        instance.ok = code // 100 == 2
        return instance


def is_private_ip(ip):
    """
    Sprawdza, czy dany adres IP należy do zakresu prywatnych adresów IP.
    Zwraca True, jeśli adres jest prywatny (za NAT), w przeciwnym razie False.
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except ValueError:
        print(f"Invalid IP address: {ip}")
        return False


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
        # Provide username
        self._send_command(f"USER {self.username}")
        print(self._get_response())

        # Provide password
        self._send_command(f"PASS {self.password}")
        res = self._get_response()
        print(res)
        if not res.ok:
            raise Exception(f"Login failed: {res.strip()}")

        print("FTP login successful.\n")

    def setup(self):
        """
        Sets binary mode, stream mode and file structure.\n
        Should happen after login and before any data transfer.
        """
        # Set binary mode
        self._send_command("TYPE I")
        type_response = self._get_response()
        print(type_response)
        if not type_response.ok:
            raise Exception(f"Failed to set TYPE: {type_response.strip()}")

        # Set stream mode
        self._send_command("MODE S")
        mode_response = self._get_response()
        print(mode_response)
        if not mode_response.ok:
            raise Exception(f"Failed to set MODE: {mode_response.strip()}")

        # Set file structure
        self._send_command("STRU F")
        stru_response = self._get_response()
        print(stru_response)
        if not stru_response.ok:
            raise Exception(f"Failed to set STRU: {stru_response.strip()}")

        print("FTP setup successful\n")

    def _send_command(self, command):
        print(f">> Sending command: {command}")
        self.control_socket.sendall((command + "\r\n").encode("utf-8"))

    def _get_response(self):
        response = self.control_socket.recv(1024).decode("utf-8")
        response_code = (
            int(response.split(" ", 1)[0]) if response.split(" ", 1)[0].isdigit() else 0
        )
        return ExtendedResponse("<< " + response, code=response_code)

    def close(self):
        try:
            self._send_command("QUIT")
            print(self._get_response())
            self.control_socket.close()
        except Exception as e:
            print(f"Can't close connection: {e}")

    def list_directory(self, path=""):
        data_socket = self._open_data_connection()
        self._send_command(f"LIST {path}")
        res = self._get_response()
        if res.code == 550:
            print("File unavailable (e.g., file not found, no access)")
        else:
            print(res)

        if res.code == 150:
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
            res = self._get_response()
            print(res)
            if not res.ok:
                return False
            data_socket.sendall(f.read())
            data_socket.close()
            res = self._get_response()
            print(res)
            return res.ok

    def download_file(self, remote_path, local_path):
        data_socket = self._open_data_connection()
        self._send_command(f"RETR {remote_path}")
        res = self._get_response()
        print(res)
        if not res.code == 150:
            print("Server didn't start data transfer\n")
            return False
        with open(local_path, "wb") as f:
            while True:
                data = data_socket.recv(1024)
                if not data:
                    break
                f.write(data)
        data_socket.close()
        res = self._get_response()
        print(res)
        if res.ok:
            return True
        else:
            return False

    def _open_data_connection(self):
        self._send_command("PASV")
        response = self._get_response()
        print(response)

        if response.code != 227:
            print("Failed to start data connection.")
            raise Exception(f"Error opening data connection: {response.strip()}")

        start = response.find("(") + 1
        end = response.find(")")
        numbers = list(map(int, response[start:end].split(",")))
        ip_address = ".".join(map(str, numbers[:4]))
        port = (numbers[4] << 8) + numbers[5]

        if is_private_ip(ip_address):
            print(
                f"Detected private IP: {ip_address}. Using server IP instead: {self.host}."
            )
        else:
            # replace provided (incorrect) ip with ip of server
            ip_address = self.host

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
    elif param2.startswith("ftp://"):
        parsed_url = urlparse(param2)
    else:
        print("Invalid FTP URL.")
        help()
        sys.exit(1)
        pass

    host = parsed_url.hostname
    port = parsed_url.port or 21
    username = parsed_url.username or "anonymous"
    password = parsed_url.password or ""
    remote_path = parsed_url.path or "/"

    client = FTPClient(host, port, username, password)

    def full_path():
        """
        joins path from url (target remote folder) and param2 (relative path and folder name to create) to get full path
        """
        return os.path.normpath(os.path.join(remote_path, param2 or "")).replace(
            "\\", "/"
        )

    def validateParams(operationType, params=[]):
        """
        Validates the parameters required for each FTP operation based on the operation type.

        Args:
            operationType (str): The type of FTP operation (e.g., "ls", "mkdir", "rmdir", "rm", "cp", "mv").
            params: A list containing the parameters for the operation.

        Returns:
            bool: True if the parameters are valid, False otherwise.
        """

        def is_valid_path(path):
            return isinstance(path, str) and len(path.strip()) > 0

        def is_valid_ftp_url(url):
            return isinstance(url, str) and url.startswith("ftp://")

        match operationType:
            case "ls":
                # Validate `path`
                if len(params) < 1:
                    print("Not enough parameters provided. Required 1")
                    return False
                if len(params) > 1:
                    print("WARN: too much parameters")
                if not is_valid_path(params[0]):
                    print("Invalid or missing 'path' for 'ls' operation.")
                    return False
            case "mkdir" | "rmdir" | "rm":
                # Validate `full_path`
                if not is_valid_path(params[0]):
                    print(
                        f"Invalid or missing 'full_path' for '{operationType}' operation."
                    )
                    return False
            case "cp":
                # Validate `param1` and `param2`
                if len(params) != 2:
                    print("This operation takes exactly 2 parameters. ")
                    return False
                if not (
                    is_valid_ftp_url(params[0]) and is_valid_path(params[1])
                ) or not (is_valid_ftp_url(params[1]) and is_valid_path(params[0])):
                    print(
                        "Invalid local_path or remote_path. One should be a remote path on FTP server (starting with ftp://) and the other should be a local path on your machine"
                    )
                    return False
            case "mv":
                # Validate `param1` and `param2`
                # TODO
                pass
            case _:
                print("Unknown operation type.")
                return False

        # If all checks pass
        return True

    try:
        client.connect()
        client.login()
        client.setup()

        target_operation = None
        match operation:
            case "ls":
                target_operation = client.list_directory(remote_path)
            case "mkdir":
                target_operation = client.make_directory(full_path())
            case "rmdir":
                target_operation = client.remove_directory(full_path())
            case "rm":
                target_operation = client.delete_file(full_path())
            case "cp":
                if param1.startswith("ftp://"):
                    target_operation = client.download_file(remote_path, param2)
                else:
                    target_operation = client.upload_file(param1, remote_path)
            case "mv":
                if param1.startswith("ftp://"):
                    # direction server->client
                    # download file
                    success = client.download_file(remote_path, param2)
                    # check if success
                    if success:
                        # remove from server
                        client.delete_file(remote_path)
                else:
                    # direction client->server
                    success = client.upload_file(param1, remote_path)
                    if success:
                        # TODO remove local file
                        pass
                    else:
                        print("Upload failed, nothing deleted.")
            case _:
                print("Unknown operation.")

        if target_operation:
            target_operation()
    except Exception as e:
        print(f"Something went wrong. \n{e}\n Closing...")
    finally:
        client.close()


# def help():
#     print(
#         """
# 1.  List Directory
#     Command: ls
#     Usage: ls <ftp_url>

# 2.  Make/create directory
#     Command: mkdir
#     Usage: mkdir <ftp_url>[remote_path] [relative_path]/<folder_name>

# 3.  Remove directory
#     Command: rmdir
#     Usage: rmdir <ftp_url>[remote_path] [relative_path]/<folder_name>

# 4.  Remove file
#     Command: rm
#     Usage: rm <ftp_url>[remote_path] [relative_path]/<file_name>

# 5.  Copy
#     Command: cp
#     Usage:  cp <ftp_url>/<remote_path>/<file/folder> <local_path>/<file/folder>
#             cp <local_path>/<file/folder> <ftp_url>/<remote_path>/<file/folder>

# 6.  Move
#     Command: mv

# """
#     )


if __name__ == "__main__":
    main()


# kod, znacznik kontunuacji(more), opis (dla użytkownika lub zinterpretować - gdy są to parametry)


# usftp cp c:\katalog\plik.txt ftp://user:pass@127.0.0.1:21/test/

# tryb ciągły?

# W zależności od tego, jakie polecenie zostanie wysłane, mogą być wymagane również dodatkowe parametry

# co jak zostanie zresetowane połączenie z serwerem w trakcie?

import socket
import sys
from urllib.parse import urlparse
import os
import ipaddress
from datetime import datetime, timedelta

# https://datatracker.ietf.org/doc/html/rfc959 (page 40) 4.2.2 Numeric  Order List of Reply Codes

TIMEZONE_OFFSET = 1


class ExtendedResponse(str):
    def __new__(cls, value: str, code: int = None, ok: bool = None):
        # Create the response (string) part
        instance = super().__new__(cls, value)
        # Add additional attributes
        instance.code = code
        instance.ok = code // 100 == 2
        return instance


def is_private_ip(ip):
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
        try:
            print(f"Connecting to {self.host}:{self.port}")
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.host, self.port))
            print(self._get_response())  # Welcome message
        except socket.gaierror:
            print(
                f"Error: Unable to resolve FTP server address: {self.host}. Please check the hostname."
            )
            sys.exit(1)
        except ConnectionRefusedError:
            print(
                f"Error: Connection refused by {self.host}:{self.port}. The server may be offline or not accepting connections."
            )
            sys.exit(1)
        except TimeoutError:
            print(
                f"Error: Connection to {self.host}:{self.port} timed out. Please try again later."
            )
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)

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
        response = ""
        response_code = None
        is_multiline = False

        while True:
            # Receive data in chunks
            data = self.control_socket.recv(1024).decode("utf-8")
            response += data

            lines = response.splitlines()

            # if no code yet get it from the first line
            if response_code is None and len(lines) > 0:
                first_line = lines[0]
                if len(first_line) >= 4 and first_line[:3].isdigit():
                    response_code = int(first_line[:3])
                    is_multiline = (
                        first_line[3] == "-"
                    )  # multi-line response is indicated by code followed by '-' (123-Text)

            # in multiline response wait for same code followed by space (that's the last line of response)
            if is_multiline and len(lines) > 0:
                last_line = lines[-1]
                if (
                    len(last_line) >= 4
                    and last_line[:3].isdigit()
                    and int(last_line[:3]) == response_code
                    and last_line[3] == " "
                ):
                    break  # End of multi-line response

            # in single-line responses, we can stop on CRLF
            if not is_multiline and "\r\n" in data:
                break

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
        res = self._get_response()
        print(res)
        if "550 Permission denied" in res:
            print(
                "Possible causes:\n1)Your account can't delete file\n2)You're attempting to delete folder with rm instead of rmdir"
            )

    def check_last_modification_time(self, remote_path):
        """
        Check the last modification time of a file on the FTP server.
        """
        self._send_command(f"MDTM {remote_path}")

        res = self._get_response()
        if res.code != 550:
            print(res)
        if res.code == 213:  # 213 -> modification time is returned successfully
            mdtm_str = res.split(" ", 2)[2].strip()
            try:
                mdtm_utc = datetime.strptime(mdtm_str, "%Y%m%d%H%M%S.%f")
            except ValueError:
                mdtm_utc = datetime.strptime(mdtm_str, "%Y%m%d%H%M%S")

            # Add the timezone offset (in hours) to the UTC time
            offset = timedelta(hours=TIMEZONE_OFFSET)
            mdtm_local = mdtm_utc + offset
            return mdtm_local
        else:
            return None

    def compare_file_size(self, remote_path, local_path):
        """
        Check the file size of a file on the FTP server and compare it with the local file size.
        Returns True if the file sizes match, otherwise False.
        """

        if os.path.exists(local_path):
            local_size = os.path.getsize(local_path)
        else:
            local_size = 0

        self._send_command(f"SIZE {remote_path}")
        res = self._get_response()
        print(res)
        if res.code == 550:
            print(f"Failed to retrieve size for file: {remote_path}\n")
            return False
        elif res.code == 213:  # 213 -> size is returned successfully
            remote_size = int(res.split(" ", 2)[2].strip())
            print(f"Remote file size: {remote_size}, Local file size: {local_size}\n")

            return remote_size == local_size
        else:
            print("Unable to compare size for files.\n")
            return False

    def upload_file(self, local_path, remote_path):
        local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path))

        # Check if the remote file exists and get its modification time
        remote_mtime = self.check_last_modification_time(remote_path)
        print(remote_mtime, local_mtime)
        if remote_mtime:
            if remote_mtime > local_mtime:
                # remote file is newer -> prompt for confirmation
                overwrite = input(
                    f"Remote file '{remote_path}' is newer ({remote_mtime}) than your local file ({local_mtime}). Overwrite? (y/N): "
                )
                if overwrite.lower() != "y":
                    print("Upload canceled.")
                    return False

        with open(local_path, "rb") as f:
            data_socket = self._open_data_connection()
            self._send_command(f"STOR {remote_path}")
            res = self._get_response()
            print(res)
            if res.code != 150:
                return False
            data_socket.sendall(f.read())
            data_socket.close()
            res = self._get_response()
            print(res)
            if res.ok:
                print("File uploaded")
            else:
                print("Upload failed")
            return res.ok

    def download_file(self, remote_path, local_path):
        # if file exists -> prompt for confirmation
        if os.path.exists(local_path):
            overwrite = input(
                f"The file '{local_path}' already exists. Do you want to overwrite it? (y/N): "
            )
            if overwrite.lower() != "y":
                print("Download aborted.\n")
                return False

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

        if res.ok and self.compare_file_size(remote_path, local_path):
            print(f"File downloaded successfully to '{local_path}'.\n")
            return True
        else:
            print("File download failed.\n")
            return False

    def _open_data_connection(self):
        self._send_command("PASV")
        response = self._get_response()
        print(response)

        if response.code != 227:
            print("Failed to start data connection.\n")
            raise Exception(f"Error opening data connection: {response.strip()}")

        start = response.find("(") + 1
        end = response.find(")")
        numbers = list(map(int, response[start:end].split(",")))
        ip_address = ".".join(map(str, numbers[:4]))
        port = (numbers[4] << 8) + numbers[5]

        if is_private_ip(ip_address):
            print(
                f"Detected private IP: {ip_address}. Using server IP instead: {self.host}.\n"
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
        print("Usage: usftp <operation> <param1> [param2]")
        sys.exit(1)

    operation = sys.argv[1]
    param1 = sys.argv[2] if len(sys.argv) > 2 else None
    param2 = sys.argv[3] if len(sys.argv) > 3 else None
    return operation, param1, param2


def validate(validators={}):
    """
    Validates parameters based on specified validation rules, with separate checks for failures and warnings.

    Args:
        validators (dict): A dictionary where keys are validation function names
                           and values are lists of parameters to validate.

    Returns:
        tuple: (success: bool, warnings: bool)
               - success: True if validation passed, False if failed.
               - warnings: True if warnings are present, False otherwise.
    """

    ### Validation functions that cause failure
    def is_valid_path(path):
        return isinstance(path, str) and len(path.strip()) > 0 and "\\" not in path

    def is_valid_ftp_url(url):
        # At least ftp prefix and hostname
        if not isinstance(url, str) or not url.startswith("ftp://"):
            return False
        parsed = urlparse(url)
        return bool(parsed.hostname)

    ### Validation functions that issue warnings
    def is_file_path(path):
        # Warn if the path does not end with a file and extension
        return "." in path.split("/")[-1]

    def is_file(path):
        return os.path.isfile(path)

    ###
    fail_validations = {
        "is_valid_path": is_valid_path,
        "is_valid_ftp_url": is_valid_ftp_url,
        "is_file": is_file,
    }

    warn_validations = {
        "is_file_path": is_file_path,
    }

    has_warning = False

    # Perform validations that cause failures
    for validator, params in validators.items():
        if validator in fail_validations:
            for param in params:
                if not fail_validations[validator](param):
                    print(f"Validation failed for '{param}' with {validator}")
                    return False, False

    # Perform validations that issue warnings
    for validator, params in validators.items():
        if validator in warn_validations:
            for param in params:
                if not warn_validations[validator](param):
                    print(
                        f"Warning: '{param}' may not follow best practices for for {validator}"
                    )
                    has_warning = True

    return True, has_warning


def validate_with_prompt(validators={}):
    """
    Wrapper for the validate function that prompts user confirmation
    if warnings are present.

    Returns:
        bool: True if operation should continue, False otherwise.
    """
    success, warnings = validate(validators)
    if not success:
        print("Validation failed. Aborting operation.")
        return False

    if warnings:
        response = (
            input("Warnings are present. Do you want to continue? (y/N): ")
            .strip()
            .lower()
        )
        if response != "y":
            print("Operation aborted by the user.")
            return False

    return True


def help():
    print(
        """
1.  List Directory
    Command: ls
    Usage: ls <ftp_url>

2.  Make/create directory
    Command: mkdir
    Usage: mkdir <ftp_url> <folder_name>
       or: mkdir <ftp_url>/<folder_name>

3.  Remove directory
    Command: rmdir
    Usage: rmdir <ftp_url> <folder_name>
       or: rmdir <ftp_url>/<folder_name>

4.  Remove file
    Command: rm
    Usage: rm <ftp_url> <file_name>
       or: rm <ftp_url>/<folder_name>

5.  Copy
    Command: cp
    Example: cp ./file.txt ftp://user:pass@localhost:21/
         or: cp ftp://user:pass@localhost:21/file.txt ./

6.  Move
    Command: mv
    Example: mv ./file.txt ftp://user:pass@localhost:21/
         or: mv ftp://user:pass@localhost:21/file.txt ./

"""
    )


def main():
    if "help" in sys.argv[1]:
        help()
        sys.exit(1)

    operation, param1, param2 = parse_command_line()

    if param1.startswith("ftp://") and validate({"is_valid_ftp_url": [param1]})[0]:
        parsed_url = urlparse(param1)
    elif param2.startswith("ftp://") and validate({"is_valid_ftp_url": [param2]})[0]:
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

    client.connect()
    try:
        client.login()
        client.setup()

        match operation:
            case "ls":
                if validate_with_prompt({"is_valid_path": [remote_path]}):
                    client.list_directory(remote_path)
            case "mkdir":
                target_path = full_path()
                if validate_with_prompt({"is_valid_path": [target_path]}):
                    client.make_directory(target_path)
            case "rmdir":
                target_path = full_path()
                if validate_with_prompt({"is_valid_path": [target_path]}):
                    client.remove_directory(target_path)
            case "rm":
                target_path = full_path()
                if validate_with_prompt(
                    {"is_valid_path": [target_path], "is_file_path": [target_path]}
                ):
                    client.delete_file(target_path)
            case "cp":
                if param1.startswith("ftp://"):
                    local_path = param2
                    filename = os.path.basename(remote_path)
                    if not param2.endswith(filename):
                        local_path = os.path.join(param2, filename).replace("\\", "/")
                    if validate_with_prompt(
                        {"is_valid_path": [remote_path, local_path]}
                    ):
                        client.download_file(remote_path, local_path)
                else:
                    filename = os.path.basename(param1)
                    if not remote_path.endswith(filename):
                        # if filename not included in path (points to directory only) append it
                        remote_path = os.path.join(remote_path, filename).replace(
                            "\\", "/"
                        )
                    if validate_with_prompt(
                        {"is_valid_path": [remote_path, param1], "is_file": [param1]}
                    ):
                        client.upload_file(param1, remote_path)
            case "mv":
                if param1.startswith("ftp://"):
                    # direction server->client
                    local_path = param2
                    filename = os.path.basename(remote_path)
                    if not param2.endswith(filename):
                        local_path = os.path.join(param2, filename).replace("\\", "/")

                    if validate_with_prompt(
                        {"is_valid_path": [remote_path, local_path]}
                    ):
                        success = client.download_file(remote_path, local_path)
                        if success:
                            client.delete_file(remote_path)
                else:
                    # direction client->server
                    filename = os.path.basename(param1)
                    if not remote_path.endswith(filename):
                        # if filename not included in path (points to directory only) append it
                        remote_path = os.path.join(remote_path, filename).replace(
                            "\\", "/"
                        )
                    if validate_with_prompt(
                        {"is_valid_path": [remote_path, param1], "is_file": [param1]}
                    ):
                        success = client.upload_file(param1, remote_path)
                        if success:
                            # remove local file
                            try:
                                os.remove(param1)
                                print(
                                    f"Local file '{param1}' has been removed after successful upload.\n"
                                )
                            except Exception as e:
                                print(f"Failed to remove local file '{param1}': {e}")
                        else:
                            print("Upload failed, nothing deleted.\n")
            case _:
                print("Unknown operation.")
                help()
    except Exception as e:
        print(f"Something went wrong. \n{e}\n Closing...")
    finally:
        client.close()


if __name__ == "__main__":
    main()

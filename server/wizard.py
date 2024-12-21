import bcrypt
from pathlib import Path
from tinydb import TinyDB, Query
import configparser


def add_user():
    """Create a simple menu for adding a user"""

    db = TinyDB("users.json")
    User = Query()

    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()

    if not username or not password:
        print("Both username and password are required!")
        return

    if not db.contains(User.username == username):
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode()
        home_dir = str(Path("./ftp") / username)

        db.insert(
            {
                "username": username,
                "password": hashed_password,
                "home": home_dir,
            }
        )
        print(f"User '{username}' added successfully!")
    else:
        print(f"User '{username}' already exists.")


def create_config():
    """create the config file"""
    config = configparser.ConfigParser()

    print(
        "Enter the following configuration settings (press Enter to accept the default value):"
    )

    port = input("Port (default 21): ").strip() or "21"
    host = input("Host (default 127.0.0.1): ").strip() or "127.0.0.1"
    passive_ports = (
        input("Passive Port Range (default 50000,50100): ").strip() or "50000,50100"
    )
    session_timeout = input("Session Timeout (default 300): ").strip() or "300"
    login_timeout = input("Login Timeout (default 30): ").strip() or "30"
    data_timeout = input("Data Timeout (default 10): ").strip() or "10"
    root_dir = input("Root Directory (default ./ftp): ").strip() or "./ftp"
    allow_anonymous = input("Allow Anonymous (default False): ").strip() or "False"

    # Asking for the config filename
    filename = (
        input("Enter filename for config (default 'ftpserver.conf'): ").strip()
        or "ftpserver.conf"
    )

    # Creating config file
    config["SERVER"] = {
        "Port": port,
        "Host": host,
        "PassivePortRange": passive_ports,
        "SessionTimeout": session_timeout,
        "LoginTimeout": login_timeout,
        "DataTimeout": data_timeout,
        "RootDirectory": root_dir,
        "AllowAnonymous": allow_anonymous,
    }

    # Save
    with open(filename, "w") as configfile:
        config.write(configfile)

    print("Configuration file created successfully!")


# Menu
def main():
    while True:
        print("\n-- Menu --")
        print("1. Add User")
        print("2. Create Config File")
        print("3. Exit")

        choice = input("Choose an option: ").strip()

        match choice:
            case "1":
                add_user()
            case "2":
                create_config()
            case "3":
                print("Exiting...")
                break
            case _:
                print("Invalid choice, please try again.")


if __name__ == "__main__":
    main()

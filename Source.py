import os
import platform
import socket
import subprocess
import sys
import time
import webbrowser
from threading import Thread

BANNER_TEXT = r"""
  ___ ____   ____ _               _            
 |_ _|  _ \ / ___| |__   ___  ___| | _____ _ __ 
  | || |_) | |   | '_ \ / _ \/ __| |/ / _ \ '__|
  | ||  __/| |___| | | |  __/ (__|   <  __/ |   
 |___|_|    \____|_| |_|\___|\___|_|\_\___|_|   
"""


def is_admin():
    """Checks if the script is currently running with administrative/root privileges."""
    os_type = platform.system()
    if os_type == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        return os.getuid() == 0


def relaunch_as_admin():
    """Relaunches the current script with administrative privileges."""
    os_type = platform.system()
    print("[*] Elevating privileges... Please accept the prompt.")
    time.sleep(1)

    try:
        if os_type == "Windows":
            import ctypes
            script = os.path.abspath(sys.argv[0])
            params = " ".join(sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
            sys.exit(0)
        else:
            script = os.path.abspath(sys.argv[0])
            cmd = ["sudo", sys.executable, script] + sys.argv[1:]
            os.execvp("sudo", cmd)
    except Exception as e:
        print(f"[ERROR] Failed to elevate privileges: {e}")
        input("\nPress ENTER to continue...")


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def show_banner():
    print(BANNER_TEXT)
    if is_admin():
        print(" [STATUS] PRIVILEGED MODE ACTIVE (ALL ACTIONS UNLOCKED)")
    else:
        print(" [STATUS] LIMITED USER MODE")
    print("-" * 65)


def get_local_ip():
    """Gets the actual primary local IP address by creating a dummy socket connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except socket.error:
            return None


def check_port(ip, port, timeout=0.5):
    """Checks if a specific network port is open on the target device."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((ip, port)) == 0:
                return True
    except Exception:
        pass
    return False


def identify_device(ip, ttl):
    """Heuristically guesses device classification using TTL indicators and open services."""
    if ttl is not None:
        if ttl > 64 and ttl <= 128:
            return "PC (Windows)"
        elif ttl <= 64:
            if check_port(ip, 22) or check_port(ip, 111) or check_port(ip, 443):
                return "PC (Linux / macOS / Server)"
            return "Mobile / Embedded Device (Android/iOS)"
    return "Unidentified Device"


def parse_ttl(stdout_str):
    """Extracts the numerical TTL token from system ping outputs."""
    try:
        for token in stdout_str.split():
            if token.lower().startswith("ttl="):
                return int(token.split("=")[1])
    except Exception:
        pass
    return None


def scan_ping(ip_prefix, host, active_devices):
    """Pings a target host and triggers a profile test if online."""
    ip = f"{ip_prefix}.{host}"
    os_type = platform.system()
    
    if os_type == "Windows":
        cmd = ["ping", "-n", "1", "-w", "800", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
        
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if result.returncode == 0:
            ttl = parse_ttl(result.stdout)
            device_type = identify_device(ip, ttl)
            
            print(f"[DEVICE ONLINE] {ip:<15} -> Classification: {device_type}")
            active_devices.append((ip, device_type))
    except Exception:
        pass


def check_wifi_ips():
    """Scans local subnets for active devices and handles profiling."""
    local_ip = get_local_ip()
    if not local_ip or local_ip == "127.0.0.1":
        print("[ERROR] Cannot scan without a valid local network connection.")
        return

    ip_parts = local_ip.split(".")
    ip_prefix = ".".join(ip_parts[:3])
    
    print(f"[*] Subnet Target: {ip_prefix}.1 to {ip_prefix}.254")
    print("[*] Launching multi-threaded identification scan (please wait)...")
    print("-" * 65)
    
    threads = []
    active_devices = []
    
    for host in range(1, 255):
        t = Thread(target=scan_ping, args=(ip_prefix, host, active_devices))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("-" * 65)
    print(f"[SUCCESS] Scan Complete. Profiled {len(active_devices)} online target(s).")


def obfuscate_ip():
    """Attempts to dynamically cycle your local network adapter's DHCP IP address."""
    os_type = platform.system()
    print("[*] Initiating DHCP IP Obfuscation/Rotation routine...")
    
    try:
        if os_type == "Windows":
            print("[*] Releasing current DHCP IP...")
            subprocess.run(["ipconfig", "/release"], stdout=subprocess.DEVNULL, check=True)
            time.sleep(2)
            print("[*] Requesting fresh IP address from router...")
            subprocess.run(["ipconfig", "/renew"], stdout=subprocess.DEVNULL, check=True)
            
        elif os_type == "Linux":
            print("[*] Restarting NetworkManager to force DHCP cycle...")
            subprocess.run(["systemctl", "restart", "NetworkManager"], check=True)
            
        elif os_type == "Darwin":  # macOS
            print("[*] Cycling Wi-Fi hardware stack...")
            subprocess.run(["ipconfig", "set", "en0", "BOOTP"], check=True)
            subprocess.run(["ipconfig", "set", "en0", "DHCP"], check=True)
            
        print("[SUCCESS] Network interface interface cycled. Check 'Get IP' for your new assignment.")
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to reset network interfaces. Try executing option manually.")


def toggle_ip_forwarding():
    """Modifies internal routing engines to toggle network IP Forwarding on/off."""
    os_type = platform.system()
    print(f"[*] Native Platform Verification: {os_type}")
    
    try:
        if os_type in ["Linux", "Darwin"]:
            sysctl_key = "net.ipv4.ip_forward" if os_type == "Linux" else "net.inet.ip.forwarding"
            current = subprocess.check_output(["sysctl", "-n", sysctl_key]).decode().strip()
            new_state = "0" if current == "1" else "1"
            
            print(f"[*] Adjusting network kernel parameter {sysctl_key} to {new_state}...")
            subprocess.run(["sysctl", "-w", f"{sysctl_key}={new_state}"], check=True)
            print(f"[SUCCESS] IP Routing engine is now {'ENABLED' if new_state == '1' else 'DISABLED'}.")

        elif os_type == "Windows":
            import winreg
            path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
            value, _ = winreg.QueryValueEx(key, "IPEnableRouter")
            
            new_state = 0 if value == 1 else 1
            print(f"[*] Writing Registry Routing Flag to {new_state}...")
            
            winreg.SetValueEx(key, "IPEnableRouter", 0, winreg.REG_DWORD, new_state)
            winreg.CloseKey(key)
            print(f"[SUCCESS] Windows Registry updated to {new_state}.")
            print("[NOTE] Windows architecture requires a system restart to apply global routing state.")
            
        else:
            print("[ERROR] Unsupported kernel platform framework.")
    except Exception as e:
        print(f"[ERROR] Failed engine toggle sequence: {e}")


def main():
    while True:
        clear()
        show_banner()

        print("[1] Get Local IP")
        print("[2] Scan Subnet & Profile Devices")
        print("[3] Obfuscate Network IP")
        print("[4] IP Forwarding")
        print("[5] Relaunch as Administrator")
        print("[6] Close Terminal\n")

        choice = input("Select Option: [~] ").strip()

        # Secret Backdoor
        if choice.lower() == "github":
            webbrowser.open("https://github.com/DuckyCashy/IPChecker")
            continue

        clear()
        show_banner()

        if choice == "1":
            ip = get_local_ip()
            if ip:
                print(f"[SUCCESS] Local IP Found: {ip}")
            else:
                print("[ERROR] Failed to find active IP assignment.")
        elif choice == "2":
            check_wifi_ips()
        elif choice == "3":
            if not is_admin():
                print("[WARNING] This operation requires Admin privileges.")
                if input("Try to relaunch as Admin now? (y/n): ").lower() == 'y':
                    relaunch_as_admin()
            else:
                obfuscate_ip()
        elif choice == "4":
            if not is_admin():
                print("[WARNING] This operation requires Admin privileges.")
                if input("Try to relaunch as Admin now? (y/n): ").lower() == 'y':
                    relaunch_as_admin()
            else:
                toggle_ip_forwarding()
        elif choice == "5":
            if is_admin():
                print("[!] Already running with Administrator / Root clearances.")
            else:
                relaunch_as_admin()
        elif choice == "6":
            print("[!] Closing Terminal...")
            time.sleep(1)
            break
        else:
            print("[!] Invalid Option.")

        print()
        input("Press ENTER to continue...")


if __name__ == "__main__":
    main()

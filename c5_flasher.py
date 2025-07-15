# === ESP32-C5 Auto Flasher Script By: AWOK ===
# BASELINE v0.1 with Centered Startup Message
# This script detects an ESP32-C5 on serial, ensures requirements are installed,
# locates required .bin files in ./bins, and flashes them with esptool.
# All imports are kept for future expansion and compatibility.

import sys                    # For interacting with the Python interpreter and argv
import subprocess             # To call pip for auto-installing/updating packages
import os                     # For path handling and directory operations
import platform               # (Not currently used) For possible OS detection
import glob                   # For matching .bin file patterns
import time                   # For time-based polling (waiting for device)
import shutil                 # Used here for terminal size and possible future file operations
import serial.tools.list_ports # For listing serial ports and detecting the ESP32
import esptool                # Main library for flashing ESP32 devices
from colorama import Fore, Style # For colored terminal output
import argparse               # For command-line argument parsing

# --- Requirement Auto-Installer ---
# Ensures all necessary Python packages are installed/up to date before importing.
REQUIRED_PACKAGES = [
    'pyserial',
    'esptool',
    'colorama'
]

def ensure_package(pkg):
    """Check for and install/upgrade a Python package if not present."""
    try:
        __import__(pkg if pkg != 'gitpython' else 'git')
    except ImportError:
        print(f"Installing missing package: {pkg}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', pkg])

def ensure_requirements():
    """Ensure all packages in REQUIRED_PACKAGES are available."""
    for pkg in REQUIRED_PACKAGES:
        ensure_package(pkg)

ensure_requirements()

# --- Helper: Find a file in ./bins by name (returns first match) ---
def find_file(name_options, bins_dir):
    """
    Search for the first file in 'bins_dir' matching one of the provided names.
    Used to find bootloader, partition table, or OTA data binaries.
    """
    for name in name_options:
        files = glob.glob(os.path.join(bins_dir, name))
        if files:
            return files[0]
    return None

# --- Main Script Logic ---
def main():
    parser = argparse.ArgumentParser(description="ESP32-C5 Auto Flasher with Bootloader and Partitions (bins subdir)")
    parser.parse_args()

    bins_dir = os.path.join(os.path.dirname(__file__), 'bins')

    if not os.path.isdir(bins_dir):
        print(Fore.RED + f"Bins directory not found: {bins_dir}\nPlease create a 'bins' folder with your .bin files." + Style.RESET_ALL)
        exit(1)

    # --- Display Centered Startup Message (Purple Text) ---
    terminal_width = shutil.get_terminal_size((80, 20)).columns  # Default to 80 if undetectable
    def center(text): return text.center(terminal_width)
    splash_lines = [
        "--  ESP32 C5 Flasher --",
        "By AWOK",
        "Inspired from LordSkeletonMans ESP32 FZEasyFlasher",
        "Shout out to JCMK for the inspiration on setting up the C5",
        ""
    ]
    # Print in purple/magenta
    print(Fore.MAGENTA + "\n" + "\n".join(center(line) for line in splash_lines) + Style.RESET_ALL)

    # --- Serial Port Detection: Wait for ESP32-C5 connection ---
    existing_ports = set([port.device for port in serial.tools.list_ports.comports()])
    print(Fore.YELLOW + "Waiting for ESP32-C5 device to be connected..." + Style.RESET_ALL)
    while True:
        current_ports = set([port.device for port in serial.tools.list_ports.comports()])
        new_ports = current_ports - existing_ports
        if new_ports:
            serial_port = new_ports.pop()
            break
        time.sleep(0.5)
    print(Fore.GREEN + f"Detected ESP32-C5 on port: {serial_port}" + Style.RESET_ALL)

    # --- Locate Required .bin Files in ./bins ---
    # Bootloader is required; should be named bootloader.bin
    bootloader = find_file(['bootloader.bin'], bins_dir)
    # Partition table is required; try both typical names
    partitions = find_file(['partition-table.bin', 'partitions.bin'], bins_dir)
    # OTA data is optional; only if present
    ota_data = find_file(['ota_data_initial.bin'], bins_dir)

    # --- Locate Main Firmware Application Binary (.bin) ---
    # Select the largest .bin file in ./bins that's not one of the above as the main firmware
    all_bins = glob.glob(os.path.join(bins_dir, "*.bin"))
    exclude = {bootloader, partitions, ota_data}
    firmware_bins = [f for f in all_bins if f not in exclude and os.path.isfile(f)]
    if not firmware_bins:
        print(Fore.RED + "No application firmware .bin file found in the 'bins' folder!" + Style.RESET_ALL)
        exit(1)
    app_bin = max(firmware_bins, key=lambda f: os.path.getsize(f))

    # --- Display Summary and Confirm Flash ---
    print(Fore.CYAN + f"\nBootloader:   {bootloader or 'NOT FOUND'}")
    print(f"Partitions:   {partitions or 'NOT FOUND'}")
    print(f"OTA Data:     {ota_data or 'NOT FOUND'}")
    print(f"App (main):   {app_bin}\n" + Style.RESET_ALL)
    if not (bootloader and partitions):
        print(Fore.RED + "Missing bootloader or partition table. Both are required for a complete flash!" + Style.RESET_ALL)
        exit(1)
    confirm = input(Fore.YELLOW + "Ready to flash these files to ESP32-C5? (y/N): " + Style.RESET_ALL)
    if confirm.strip().lower() != 'y':
        print("Aborting.")
        exit(0)

    # --- Build esptool Arguments: Set Offsets for ESP32-C5 Flash ---
    # Note: Bootloader at 0x2000 per your last request
    esptool_args = [
        '--chip', 'esp32c5',
        '--port', serial_port,
        '--baud', '921600',
        '--before', 'default_reset',
        '--after', 'hard_reset',
        'write_flash', '-z',
        '0x2000', bootloader,        # Bootloader binary at offset 0x2000
        '0x8000', partitions,        # Partition table at 0x8000
    ]
    if ota_data:
        esptool_args += ['0xd000', ota_data]    # OTA data (optional) at 0xd000
    esptool_args += ['0x10000', app_bin]        # Main application at 0x10000

    # --- Flash the ESP32-C5 ---
    print(Fore.YELLOW + "Flashing ESP32-C5 with bootloader, partition table, and application..." + Style.RESET_ALL)
    try:
        esptool.main(esptool_args)
        print(Fore.GREEN + "Flashing complete!" + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"Flashing failed: {e}" + Style.RESET_ALL)

# --- Script Entry Point ---
if __name__ == "__main__":
    main()
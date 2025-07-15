import os
import platform
#from git import Repo
import glob
import time
import shutil
import serial.tools.list_ports
import requests
import json
import esptool
from colorama import Fore, Style
from pathlib import Path
import git
import argparse

def find_new_serial_port(existing_ports):
    print(Fore.YELLOW + "Waiting for ESP32-C5 device to be connected..." + Style.RESET_ALL)
    while True:
        current_ports = set([port.device for port in serial.tools.list_ports.comports()])
        new_ports = current_ports - existing_ports
        if new_ports:
            return new_ports.pop()
        time.sleep(0.5)

def find_file(name_options):
    for name in name_options:
        files = glob.glob(os.path.join(os.path.dirname(__file__), name))
        if files:
            return files[0]
    return None

def main():
    parser = argparse.ArgumentParser(description="ESP32-C5 Auto Flasher with Bootloader and Partitions")
    parser.parse_args()

    # Detect initial serial ports
    existing_ports = set([port.device for port in serial.tools.list_ports.comports()])
    serial_port = find_new_serial_port(existing_ports)
    print(Fore.GREEN + f"Detected ESP32-C5 on port: {serial_port}" + Style.RESET_ALL)

    # Find required .bin files
    bootloader = find_file(['bootloader.bin'])
    partitions = find_file(['partition-table.bin', 'partitions.bin'])
    ota_data = find_file(['ota_data_initial.bin'])  # Optional

    # Find main firmware .bin (the largest one not already used)
    all_bins = glob.glob(os.path.join(os.path.dirname(__file__), "*.bin"))
    exclude = {bootloader, partitions, ota_data}
    firmware_bins = [f for f in all_bins if f not in exclude and os.path.isfile(f)]
    if not firmware_bins:
        print(Fore.RED + "No application firmware .bin file found in the folder!" + Style.RESET_ALL)
        exit(1)
    app_bin = max(firmware_bins, key=lambda f: os.path.getsize(f))

    # Summary/confirmation
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

    # Build esptool flashing args with correct offsets and settings
    esptool_args = [
        '--chip', 'esp32c5',
        '--port', serial_port,
        '--baud', '921600',
        '--before', 'default_reset',
        '--after', 'hard_reset',
        '--flash_mode', 'qio',
        '--flash_freq', '80m',
        '--flash_size', '4MB',
        'write_flash', '-z',
        '0x0', bootloader,
        '0x8000', partitions,
    ]
    if ota_data:
        esptool_args += ['0xd000', ota_data]
    esptool_args += ['0x10000', app_bin]

    print(Fore.YELLOW + "Flashing ESP32-C5 with bootloader, partition table, and application..." + Style.RESET_ALL)
    try:
        esptool.main(esptool_args)
        print(Fore.GREEN + "Flashing complete!" + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"Flashing failed: {e}" + Style.RESET_ALL)

if __name__ == "__main__":
    main()
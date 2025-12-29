import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
import serial.tools.list_ports
import subprocess
import os
import re

# ================= CONFIG =================

FW_VERSION_URL = "https://raw.githubusercontent.com/Archer2121/Macropad/main/version.txt"
FW_BIN_URL = "https://raw.githubusercontent.com/Archer2121/Macropad/main/main/build/esp32.esp32.lolin_s3/main.ino.bin"

BIN_FILE = "macropad_firmware.bin"

# ================= HELPERS =================

def parse_version(v):
    return tuple(map(int, re.findall(r"\d+", v)))

def is_newer(remote, local):
    return parse_version(remote) > parse_version(local)

def find_device():
    for i in range(1, 255):
        ip = f"192.168.1.{i}"
        try:
            r = requests.get(f"http://{ip}/version", timeout=0.25)
            if r.status_code == 200:
                return ip, r.text.strip()
        except:
            pass
    return None, None

def get_latest_version():
    r = requests.get(FW_VERSION_URL, timeout=3)
    return r.text.strip()

# ================= GUI =================

class MacropadApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Macropad Firmware Updater")
        self.geometry("460x320")
        self.resizable(False, False)

        self.status = tk.StringVar(value="Idle")
        self.progress = tk.IntVar(value=0)
        self.device_ip = None
        self.device_version = None
        self.latest_version = None

        ttk.Label(self, text="Macropad Firmware Manager", font=("Segoe UI", 15)).pack(pady=10)

        self.info = ttk.Label(self, text="Checking firmware versions...")
        self.info.pack()

        self.progressbar = ttk.Progressbar(self, length=400, variable=self.progress)
        self.progressbar.pack(pady=10)

        ttk.Label(self, textvariable=self.status).pack()

        ttk.Button(self, text="Check Versions", command=self.check_versions).pack(pady=5)
        ttk.Button(self, text="Update via Wi-Fi (OTA)", command=self.ota_wifi).pack(pady=5)
        ttk.Button(self, text="Update via USB (COM)", command=self.ota_usb).pack(pady=5)

        self.combobox = ttk.Combobox(self, state="readonly")
        self.combobox.pack(pady=5)
        self.refresh_ports()

        ttk.Button(self, text="Refresh COM Ports", command=self.refresh_ports).pack(pady=5)

        self.check_versions()

    # ---------- UI Helpers ----------

    def reset_progress(self):
        self.progress.set(0)
        self.update_idletasks()

    def set_status(self, msg):
        self.status.set(msg)
        self.update_idletasks()

    # ---------- Version Checking ----------

    def check_versions(self):
        threading.Thread(target=self._check_versions).start()

    def _check_versions(self):
        try:
            self.set_status("Checking latest firmware...")
            self.latest_version = get_latest_version()

            self.set_status("Searching for device...")
            self.device_ip, self.device_version = find_device()

            if not self.device_ip:
                self.info.config(text=f"Latest firmware: {self.latest_version} | Device not found")
                self.set_status("Idle")
                return

            if is_newer(self.latest_version, self.device_version):
                self.info.config(
                    text=f"Device: {self.device_version} | Latest: {self.latest_version}  → UPDATE AVAILABLE"
                )
            else:
                self.info.config(
                    text=f"Device: {self.device_version} | Latest: {self.latest_version}  ✓ Up to date"
                )

            self.set_status("Idle")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------- Firmware Download ----------

    def download_firmware(self):
        self.set_status("Downloading firmware...")
        self.reset_progress()

        r = requests.get(FW_BIN_URL, stream=True)
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(BIN_FILE, "wb") as f:
            for chunk in r.iter_content(4096):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                self.progress.set(int((downloaded / total) * 100))
                self.update_idletasks()

        self.progress.set(100)

    # ---------- OTA Wi-Fi ----------

    def ota_wifi(self):
        threading.Thread(target=self._ota_wifi).start()

    def _ota_wifi(self):
        if not self.device_ip:
            messagebox.showerror("Error", "Device not found on Wi-Fi")
            return

        if not is_newer(self.latest_version, self.device_version):
            messagebox.showinfo("No Update Needed", "Device is already up to date")
            return

        try:
            self.set_status("Enabling OTA...")
            requests.get(f"http://{self.device_ip}/ota", timeout=2)
            messagebox.showinfo(
                "OTA Ready",
                "OTA enabled on device for 60 seconds.\n\nUpload firmware now."
            )
            self.set_status("Idle")
        except:
            messagebox.showerror("Error", "Failed to trigger OTA")

    # ---------- OTA USB ----------

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.combobox["values"] = [p.device for p in ports]
        if ports:
            self.combobox.current(0)

    def ota_usb(self):
        threading.Thread(target=self._ota_usb).start()

    def _ota_usb(self):
        port = self.combobox.get()
        if not port:
            messagebox.showerror("Error", "No COM port selected")
            return

        if self.device_version and not is_newer(self.latest_version, self.device_version):
            messagebox.showinfo("No Update Needed", "Device is already up to date")
            return

        try:
            # Download
            self.download_firmware()

            # Flash
            self.set_status("Preparing flash...")
            self.reset_progress()
            self.progress.set(20)

            self.set_status("Flashing firmware...")
            process = subprocess.Popen(
                [
                    "esptool",
                    "--chip", "esp32s3",
                    "--port", port,
                    "--baud", "460800",
                    "write_flash", "0x0", BIN_FILE
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            for line in process.stdout:
                if "Writing at" in line:
                    self.progress.set(60)
                elif "Hash of data verified" in line:
                    self.progress.set(90)
                self.update_idletasks()

            process.wait()
            self.progress.set(100)
            self.set_status("Update complete")
            messagebox.showinfo("Success", "Firmware updated successfully!")

        except Exception as e:
            messagebox.showerror("Error", str(e))

        finally:
            if os.path.exists(BIN_FILE):
                os.remove(BIN_FILE)

# ================= RUN =================

if __name__ == "__main__":
    MacropadApp().mainloop()

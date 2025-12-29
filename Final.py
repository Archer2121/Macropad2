import os, threading, subprocess, time, json
import requests
import serial, serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# ================= CONFIG =================
CHIP = "esp32s3"
FLASH_BAUD = "460800"
SERIAL_BAUD = 115200

FW_DIR = "firmware"
os.makedirs(FW_DIR, exist_ok=True)

VERSION_URL = "https://raw.githubusercontent.com/Archer2121/Macropad/main/version.txt"
FW_BASE_URL = "https://raw.githubusercontent.com/Archer2121/Macropad/main/main/build/esp32.esp32.lolin_s3"

FILES = {
    "bootloader": ("bootloader.bin", "0x0000"),
    "partitions": ("partitions.bin", "0x8000"),
    "boot_app0": ("boot_app0.bin", "0xE000"),
    "app": ("firmware.bin", "0x10000"),
}
# ==========================================

def find_macropad_port():
    for p in serial.tools.list_ports.comports():
        if p.vid == 0x303A:
            return p.device
        desc = (p.description or "").lower()
        if "esp32" in desc or "cdc" in desc:
            return p.device
    return None

class MacropadApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LOLIN S3 Macropad Control Center")
        self.geometry("920x640")

        self.ser = None
        self.port = tk.StringVar()
        self.status = tk.StringVar(value="Disconnected")
        self.remote_version = tk.StringVar(value="Unknown")

        self.build_ui()
        self.auto_detect()
        threading.Thread(target=self.check_version, daemon=True).start()

    # ---------- UI ----------
    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)

        ttk.Label(top, text="Device:").pack(side="left")
        self.port_box = ttk.Combobox(top, textvariable=self.port, width=20)
        self.port_box.pack(side="left", padx=5)

        ttk.Button(top, text="Refresh", command=self.auto_detect).pack(side="left")
        ttk.Button(top, text="Connect", command=self.connect_serial).pack(side="left", padx=5)

        ttk.Label(top, textvariable=self.status).pack(side="right")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.build_serial_tab()
        self.build_flash_tab()
        self.build_macro_tab()

    # ---------- Serial ----------
    def build_serial_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Serial Monitor")

        self.serial_box = scrolledtext.ScrolledText(tab, height=28)
        self.serial_box.pack(fill="both", expand=True)

        bottom = ttk.Frame(tab)
        bottom.pack(fill="x")

        self.serial_entry = ttk.Entry(bottom)
        self.serial_entry.pack(side="left", fill="x", expand=True, padx=5)

        ttk.Button(bottom, text="Send", command=self.send_serial).pack(side="right")

    # ---------- Firmware ----------
    def build_flash_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Firmware")

        ttk.Label(tab, text="Firmware Update", font=("Segoe UI", 12, "bold")).pack()
        ttk.Label(tab, textvariable=self.remote_version).pack()

        self.progress = ttk.Progressbar(tab, length=400)
        self.progress.pack(pady=5)

        ttk.Button(tab, text="Download + Flash Latest", command=self.flash_firmware).pack()

        self.flash_log = scrolledtext.ScrolledText(tab, height=18)
        self.flash_log.pack(fill="both", expand=True, padx=10)

    # ---------- Macros ----------
    def build_macro_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Macros")

        ttk.Label(tab, text="Button 1 (GPIO 2)").pack()
        self.m1 = ttk.Entry(tab, width=70)
        self.m1.pack(pady=4)

        ttk.Label(tab, text="Button 2 (GPIO 4)").pack()
        self.m2 = ttk.Entry(tab, width=70)
        self.m2.pack(pady=4)

        ttk.Button(tab, text="Send to Device", command=self.send_macros).pack(pady=10)

    # ---------- Device ----------
    def auto_detect(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        auto = find_macropad_port()
        self.port_box["values"] = ports
        if auto:
            self.port.set(auto)
            self.status.set("Macropad detected")
        elif ports:
            self.port.set(ports[0])
            self.status.set("Select device")

    def connect_serial(self):
        try:
            self.ser = serial.Serial(self.port.get(), SERIAL_BAUD, timeout=0.1)
            self.status.set("Connected")
            threading.Thread(target=self.read_serial, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def read_serial(self):
        while self.ser:
            try:
                line = self.ser.readline().decode(errors="ignore")
                if line:
                    self.serial_box.insert(tk.END, line)
                    self.serial_box.see(tk.END)
            except:
                break

    def send_serial(self):
        if self.ser:
            self.ser.write((self.serial_entry.get() + "\n").encode())
            self.serial_entry.delete(0, tk.END)

    # ---------- GitHub Firmware ----------
    def check_version(self):
        try:
            v = requests.get(VERSION_URL, timeout=5).text.strip()
            self.remote_version.set(f"Latest firmware: {v}")
        except:
            self.remote_version.set("Firmware version unavailable")

    def download_firmware(self):
        self.flash_log.insert(tk.END, "Downloading firmware...\n")
        mapping = {
            "bootloader.bin": "bootloader.bin",
            "partitions.bin": "partitions.bin",
            "boot_app0.bin": "boot_app0.bin",
            "main.ino.bin": "firmware.bin",
        }

        for src, dst in mapping.items():
            url = f"{FW_BASE_URL}/{src}"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            with open(os.path.join(FW_DIR, dst), "wb") as f:
                f.write(r.content)

    # ---------- Flash ----------
    def flash_firmware(self):
        threading.Thread(target=self._flash_thread, daemon=True).start()

    def _flash_thread(self):
        try:
            self.progress["value"] = 0

            if self.ser and self.ser.is_open:
                self.ser.close()
                self.ser = None
                time.sleep(0.5)

            self.download_firmware()
            self.progress["value"] = 20

            subprocess.run(
                ["esptool", "--chip", CHIP, "--port", self.port.get(),
                 "--before", "default-reset", "--after", "hard-reset", "erase-flash"],
                check=True
            )

            self.progress["value"] = 40

            cmd = ["esptool", "--chip", CHIP, "--port", self.port.get(),
                   "--baud", FLASH_BAUD,
                   "--before", "default-reset", "--after", "hard-reset",
                   "write-flash"]

            for _, (fname, addr) in FILES.items():
                cmd += [addr, os.path.join(FW_DIR, fname)]

            subprocess.run(cmd, check=True)
            self.progress["value"] = 100
            self.flash_log.insert(tk.END, "✔ Firmware updated successfully\n")

        except Exception as e:
            self.flash_log.insert(tk.END, f"ERROR: {e}\n")
            self.progress["value"] = 0

    # ---------- Macros ----------
    def send_macros(self):
        if not self.ser:
            return
        payload = json.dumps({"btn1": self.m1.get(), "btn2": self.m2.get()})
        self.ser.write(f"MACRO:{payload}\n".encode())

# ================= RUN =================
MacropadApp().mainloop()

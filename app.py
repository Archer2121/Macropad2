import json, requests, tkinter as tk
from tkinter import filedialog

DEVICE="http://macropad.local"

def ota():
 f=filedialog.askopenfilename()
 if f:
  requests.post(f"{DEVICE}/update",files={"firmware":open(f,"rb")})

root=tk.Tk(); root.title("Macropad OTA")
tk.Button(root,text="Upload Firmware",command=ota).pack()
root.mainloop()

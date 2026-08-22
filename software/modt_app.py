import sys
import os
import time
import threading
import json
import math
import copy
from zlib import adler32
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# PyUSB import
try:
    import usb.core
    import usb.util
except ImportError:
    usb = None

# Vendor/Product ID for MOD-t
VENDOR_ID = 0x2b75
PRODUCT_IDS = (0x0002, 0x0003)

class ModTApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MOD-t Desktop Printer Utility")
        self.root.geometry("760x620")
        self.root.minsize(680, 560)

        # Connection & state variables
        self.dev = None
        self.connected = False
        self.status_data = {}
        self.is_printing = False
        self.print_progress_val = 0.0
        self.print_thread = None
        self.stop_print_flag = False

        # Apply standard styles
        self.setup_styles()
        self.create_widgets()

        # Start background polling thread
        self.poll_active = True
        self.poll_thread = threading.Thread(target=self.background_poll, daemon=True)
        self.poll_thread.start()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Base colors and surfaces
        bg = '#EEF4FF'
        panel = '#FFFFFF'
        panel_alt = '#F8FAFC'
        border = '#DDE8F7'
        text = '#0F172A'
        muter = '#475569'
        primary = '#2563EB'
        primary_dark = '#1D4ED8'
        success = '#059669'
        danger = '#DC2626'

        self.root.configure(bg=bg)
        style.configure('.', background=bg, foreground=text, font=('Arial', 10))
        style.configure('Card.TFrame', background=panel)
        style.configure('Panel.TFrame', background=panel_alt)
        style.configure('TLabelframe', background=bg, foreground=text)
        style.configure('TLabelframe.Label', background=bg, foreground=text, font=('Arial', 10, 'bold'))
        style.configure('TLabel', background=bg, foreground=text)
        style.configure('Muted.TLabel', foreground=muter, background=bg)
        style.configure('Title.TLabel', font=('Arial', 21, 'bold'), foreground=primary, background=bg)
        style.configure('TButton', font=('Arial', 10, 'bold'), borderwidth=0, padding=8)
        style.configure('Action.TButton', background=primary, foreground='white')
        style.map('Action.TButton', background=[('active', primary_dark)], foreground=[('active', 'white')])
        style.configure('Ghost.TButton', background=panel, foreground=text)
        style.map('Ghost.TButton', background=[('active', panel_alt)])
        style.configure('Success.TLabel', foreground=success, font=('Arial', 10, 'bold'))
        style.configure('Error.TLabel', foreground=danger, font=('Arial', 10, 'bold'))
        style.configure('TCheckbutton', background=bg, foreground=text)
        style.configure('Horizontal.TProgressbar', troughcolor='#E2E8F0', background=primary, thickness=10)

    def create_widgets(self):
        self.root.configure(bg='#EEF4FF')

        header_frame = ttk.Frame(self.root, padding=(20, 18, 20, 12), style='Card.TFrame')
        header_frame.pack(fill=tk.X, padx=18, pady=(18, 0))

        title_label = ttk.Label(header_frame, text="MOD-t Operations", style='Title.TLabel')
        title_label.pack(side=tk.LEFT)

        self.conn_status_label = ttk.Label(header_frame, text="● Disconnected", foreground='#DC2626', font=('Arial', 10, 'bold'))
        self.conn_status_label.pack(side=tk.RIGHT, padx=8)

        main_frame = ttk.Frame(self.root, padding=(18, 14, 18, 18))
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_frame, style='Card.TFrame', padding=14)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        telemetry_header = ttk.Label(left_frame, text="Telemetry", style='Section.TLabel', font=('Arial', 11, 'bold'))
        telemetry_header.pack(anchor=tk.W, pady=(0, 8))

        telemetry_grid = ttk.Frame(left_frame, style='Panel.TFrame', padding=12)
        telemetry_grid.pack(fill=tk.X)

        self.lbl_temp = ttk.Label(telemetry_grid, text="Hotend Temp: -- °C", font=('Arial', 11, 'bold'))
        self.lbl_temp.pack(anchor=tk.W, pady=4)
        self.lbl_state = ttk.Label(telemetry_grid, text="Printer State: --")
        self.lbl_state.pack(anchor=tk.W, pady=4)
        self.lbl_x = ttk.Label(telemetry_grid, text="X Position: -- mm")
        self.lbl_x.pack(anchor=tk.W, pady=4)
        self.lbl_y = ttk.Label(telemetry_grid, text="Y Position: -- mm")
        self.lbl_y.pack(anchor=tk.W, pady=4)
        self.lbl_z = ttk.Label(telemetry_grid, text="Z Position: -- mm")
        self.lbl_z.pack(anchor=tk.W, pady=(4, 0))

        raw_header = ttk.Label(left_frame, text="Raw Response Details", style='Section.TLabel', font=('Arial', 11, 'bold'))
        raw_header.pack(anchor=tk.W, pady=(14, 8))

        self.txt_telemetry = tk.Text(left_frame, height=14, width=36, font=('Courier', 9), bg='#F8FAFC', fg='#0F172A', wrap=tk.WORD, relief=tk.FLAT, borderwidth=1, highlightthickness=1, highlightbackground='#DDE8F7')
        self.txt_telemetry.pack(fill=tk.BOTH, expand=True)
        self.txt_telemetry.insert(tk.END, "Waiting for connection...")
        self.txt_telemetry.config(state=tk.DISABLED)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        fil_frame = ttk.Frame(right_frame, style='Card.TFrame', padding=12)
        fil_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(fil_frame, text="Filament", style='Section.TLabel', font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 8))
        self.btn_load = ttk.Button(fil_frame, text="Load Filament (210°C)", style='Ghost.TButton', command=self.load_filament)
        self.btn_load.pack(fill=tk.X, pady=3)
        self.btn_unload = ttk.Button(fil_frame, text="Unload Filament", style='Ghost.TButton', command=self.unload_filament)
        self.btn_unload.pack(fill=tk.X, pady=3)

        job_frame = ttk.Frame(right_frame, style='Card.TFrame', padding=12)
        job_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        ttk.Label(job_frame, text="Print Job", style='Section.TLabel', font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 8))

        self.btn_select_file = ttk.Button(job_frame, text="Select G-Code File", style='Ghost.TButton', command=self.select_file)
        self.btn_select_file.pack(fill=tk.X, pady=(0, 6))
        self.selected_file_label = ttk.Label(job_frame, text="No file selected", font=('Arial', 9, 'italic'), wraplength=260, justify=tk.LEFT)
        self.selected_file_label.pack(anchor=tk.W, pady=(0, 6))

        self.optimize_var = tk.BooleanVar(value=True)
        self.chk_optimize = ttk.Checkbutton(job_frame, text="Optimize G-code on the fly", variable=self.optimize_var)
        self.chk_optimize.pack(anchor=tk.W, pady=(0, 8))

        self.btn_print = ttk.Button(job_frame, text="Send to Printer", style='Action.TButton', command=self.start_print)
        self.btn_print.pack(fill=tk.X, pady=(0, 6))
        self.btn_stop = ttk.Button(job_frame, text="Cancel Send/Job", style='Ghost.TButton', command=self.stop_print, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ttk.Progressbar(job_frame, orient='horizontal', mode='determinate', length=300, style='Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))
        self.progress_label = ttk.Label(job_frame, text='Progress: 0.0%')
        self.progress_label.pack(anchor=tk.CENTER)

        self.clear_nozzle_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'clearnozzle.gcode'))
        self.btn_clear_nozzle = ttk.Button(job_frame, text='Load bundled clearnozzle.gcode', style='Ghost.TButton', command=self.load_clear_nozzle_file)
        self.btn_clear_nozzle.pack(fill=tk.X, pady=(12, 0))

    # background status polling loop
    def background_poll(self):
        while self.poll_active:
            if not self.connected or not self.dev:
                self.try_connect()
            else:
                try:
                    # Write status request
                    self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
                    data = self.read_modt_response(0x83)
                    if data:
                        self.parse_status(data)
                except Exception as e:
                    self.connected = False
                    self.dev = None
                    self.update_status_ui_disconnected()
            time.sleep(2)

    def try_connect(self):
        if not usb:
            # PyUSB (or its native backend) not available in this runtime
            self.update_log("PyUSB or libusb is not installed correctly.")
            return

        try:
            # Try any known product IDs (normal mode and DFU/recovery mode)
            found = None
            for pid in PRODUCT_IDS:
                dev = usb.core.find(idVendor=VENDOR_ID, idProduct=pid)
                if dev is not None:
                    found = dev
                    break

            if found is not None:
                try:
                    found.set_configuration()
                except Exception:
                    # Some backends or states may raise when setting configuration;
                    # allow the device object to be used anyway if possible.
                    pass
                self.dev = found
                self.connected = True
                self.root.after(0, self.update_status_ui_connected)
            else:
                self.connected = False
                self.root.after(0, self.update_status_ui_disconnected)
        except Exception:
            # On any error, mark disconnected and keep polling; background_poll will retry.
            self.connected = False
            self.root.after(0, self.update_status_ui_disconnected)

    def read_modt_response(self, ep):
        try:
            raw = self.dev.read(ep, 64, timeout=1000)
            text = ''.join(map(chr, raw))
            fulltext = text
            while len(raw) == 64:
                raw = self.dev.read(ep, 64, timeout=1000)
                text = ''.join(map(chr, raw))
                fulltext += text
            return fulltext
        except Exception:
            return None

    def parse_status(self, raw_str):
        try:
            self.status_data = json.loads(raw_str.strip())
            status = self.status_data.get("status", {})
            
            temp = status.get("temperature", "--")
            state = status.get("state", "--")
            pos = status.get("position", {})
            x = pos.get("x", "--")
            y = pos.get("y", "--")
            z = pos.get("z", "--")

            # Update labels safely in Tkinter main thread
            self.root.after(0, lambda: self.update_telemetry_labels(temp, state, x, y, z, raw_str))
        except Exception:
            pass

    def update_telemetry_labels(self, temp, state, x, y, z, raw_json):
        self.lbl_temp.config(text=f"Hotend Temp: {temp} °C")
        self.lbl_state.config(text=f"Printer State: {state}")
        self.lbl_x.config(text=f"X Position: {x} mm")
        self.lbl_y.config(text=f"Y Position: {y} mm")
        self.lbl_z.config(text=f"Z Position: {z} mm")

        self.txt_telemetry.config(state=tk.NORMAL)
        self.txt_telemetry.delete("1.0", tk.END)
        self.txt_telemetry.insert(tk.END, raw_json)
        self.txt_telemetry.config(state=tk.DISABLED)

    def update_status_ui_connected(self):
        self.conn_status_label.config(text="● Connected", foreground="#059669")

    def update_status_ui_disconnected(self):
        self.conn_status_label.config(text="● Disconnected", foreground="#E11D48")
        self.lbl_temp.config(text="Hotend Temp: -- °C")
        self.lbl_state.config(text="Printer State: --")
        self.lbl_x.config(text="X Position: -- mm")
        self.lbl_y.config(text="Y Position: -- mm")
        self.lbl_z.config(text="Z Position: -- mm")
        
        self.txt_telemetry.config(state=tk.NORMAL)
        self.txt_telemetry.delete("1.0", tk.END)
        self.txt_telemetry.insert(tk.END, "Disconnected. Connect MOD-t via USB...")
        self.txt_telemetry.config(state=tk.DISABLED)

    def update_log(self, text):
        self.txt_telemetry.config(state=tk.NORMAL)
        self.txt_telemetry.insert(tk.END, f"\n{text}")
        self.txt_telemetry.config(state=tk.DISABLED)

    def load_filament(self):
        if not self.connected or not self.dev:
            messagebox.showerror("Error", "No printer connected.")
            return
        try:
            self.dev.write(2, bytearray.fromhex('24690096ff'))
            self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":9},"data":{"command":{"idx":52,"name":"load_initiate"}}};')
            messagebox.showinfo("Filament", "Filament load command sent. The hotend will begin preheating.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send command: {e}")

    def unload_filament(self):
        if not self.connected or not self.dev:
            messagebox.showerror("Error", "No printer connected.")
            return
        try:
            self.dev.write(2, bytearray.fromhex('246c0093ff'))
            self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":11},"data":{"command":{"idx":51,"name":"unload_initiate"}}};')
            messagebox.showinfo("Filament", "Filament unload command sent. The hotend will begin preheating.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send command: {e}")

    def load_clear_nozzle_file(self):
        if not os.path.isfile(self.clear_nozzle_path):
            messagebox.showerror("Missing file", "clearnozzle.gcode was not found in the project root.")
            return
        self.selected_file_label.config(text=self.clear_nozzle_path)
        messagebox.showinfo("Clear Nozzle", f"Loaded bundled clearnozzle.gcode:\n{self.clear_nozzle_path}")

    def select_file(self):
        fname = filedialog.askopenfilename(filetypes=[("G-code Files", "*.gcode"), ("All Files", "*.*")])
        if fname:
            self.selected_file_label.config(text=fname)

    def start_print(self):
        fname = self.selected_file_label.cget("text")
        if not fname or fname == "No file selected" or not os.path.isfile(fname):
            messagebox.showerror("Error", "Please select a valid G-code file first.")
            return

        if not self.connected or not self.dev:
            messagebox.showerror("Error", "Printer is not connected.")
            return

        self.btn_print.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_select_file.config(state=tk.DISABLED)
        self.chk_optimize.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Initializing print...")

        self.stop_print_flag = False
        self.print_thread = threading.Thread(target=self.print_worker, args=(fname,), daemon=True)
        self.print_thread.start()

    def stop_print(self):
        self.stop_print_flag = True
        self.btn_stop.config(state=tk.DISABLED)

    def print_worker(self, fname):
        # 1. Optimize G-code if checked
        if self.optimize_var.get():
            self.root.after(0, lambda: self.progress_label.config(text="Optimizing G-code..."))
            opt_filename = fname.replace(".gcode", "_optimized.gcode")
            try:
                self.run_gcode_optimization(fname, opt_filename)
                fname_to_send = opt_filename
            except Exception as e:
                self.root.after(0, lambda: messagebox.showwarning("Warning", f"G-code optimization failed, sending original file. Error: {e}"))
                fname_to_send = fname
        else:
            fname_to_send = fname

        try:
            # Adler32 checksum & file size
            size = os.path.getsize(fname_to_send)
            checksum = adler32_checksum(fname_to_send)

            with open(fname_to_send, "rb") as f:
                gcode_data = f.read()

            # Preamble commands
            self.dev.write(2, bytearray.fromhex('246a0095ff'))
            self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":3},"data":{"command":{"idx":0,"name":"bio_get_version"}}};')
            self.read_modt_response(0x81)

            self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
            self.read_modt_response(0x83)

            # Start writing actual G-code metadata
            self.dev.write(4, f'{{"metadata":{{"version":1,"type":"file_push"}},"file_push":{{"size":{size},"adler32":{checksum},"job_id":""}}}}')
            
            # Send file in chunks of 5120 bytes
            chunk_size = 5120
            start = 0
            counter = 0
            
            while start < size:
                if self.stop_print_flag:
                    self.root.after(0, lambda: messagebox.showinfo("Print Cancelled", "G-code transmission stopped by user."))
                    break

                end = min(start + chunk_size, size)
                block = gcode_data[start:end]

                counter += 1
                if counter >= 20:
                    self.read_modt_response(0x83)
                    counter = 0

                self.dev.write(4, block)
                if start == 0:
                    self.read_modt_response(0x83)

                start += chunk_size
                progress = (start / size) * 100
                progress = min(progress, 100.0)

                # Update UI progress
                self.root.after(0, lambda p=progress: self.update_progress(p))

            if not self.stop_print_flag:
                self.root.after(0, lambda: messagebox.showinfo("Print Started", "G-code sent successfully! The printer will begin printing now."))

        except Exception as e:
            self.root.after(0, lambda error_msg=str(e): messagebox.showerror("Print Error", f"Failed to send G-code: {error_msg}"))
        
        # Clean up temporary optimized file
        if self.optimize_var.get() and os.path.exists(opt_filename):
            try:
                os.remove(opt_filename)
            except Exception:
                pass

        # Reset button states
        self.root.after(0, self.reset_print_ui)

    def update_progress(self, val):
        self.progress_bar["value"] = val
        self.progress_label.config(text=f"Sending: {val:.1f}%")

    def reset_print_ui(self):
        self.btn_print.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_select_file.config(state=tk.NORMAL)
        self.chk_optimize.config(state=tk.NORMAL)

    def run_gcode_optimization(self, infname, outfname):
        # Direct port of the logic in optimize_gcode.py
        ERRORTHRESH = 0.150
        indices = {'G': 0, 'F': 1, 'X': 2, 'Y': 3, 'Z': 4, 'E': 5}
        curXYZ = [0, 0, 0]
        curE = 0
        newSequence = True
        lastF = -1

        def writeGcode(outFile, XYZ, E, F):
            nonlocal curXYZ, curE, lastF
            outline = 'G1'
            if lastF != F:
                outline += ' F' + str(F)
            lastF = F
            if XYZ[0] != curXYZ[0]:
                outline += ' X' + str(XYZ[0])
            if XYZ[1] != curXYZ[1]:
                outline += ' Y' + str(XYZ[1])
            if XYZ[2] != curXYZ[2]:
                outline += ' Z' + str(XYZ[2])
            if E != curE:
                outline += ' E' + str(E)
            outline += '\n'
            outFile.write(outline)
            curXYZ = copy.deepcopy(XYZ)
            curE = copy.deepcopy(E)

        def cross(a, b):
            return [
                a[1]*b[2] - a[2]*b[1],
                a[2]*b[0] - a[0]*b[2],
                a[0]*b[1] - a[1]*b[0]
            ]

        def mag(a):
            return math.sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])

        # Sequence state variables
        sequenceXYZ = []
        sequenceE = []
        sequenceFeedrate = 0
        sequenceExtruding = 0
        nextXYZ = [0, 0, 0]
        nextE = 0

        def initSequence(flags, args, curXYZ_p, curE_p):
            nonlocal newSequence, sequenceXYZ, sequenceE, sequenceFeedrate, sequenceExtruding, nextXYZ, nextE
            if flags[1]:
                sequenceFeedrate = args[1]
            nextXYZ = copy.deepcopy(curXYZ_p)
            nextE = copy.deepcopy(curE_p)
            if flags[2]:
                nextXYZ[0] = args[2]
            if flags[3]:
                nextXYZ[1] = args[3]
            if flags[4]:
                nextXYZ[2] = args[4]
            if flags[5]:
                nextE = args[5]
            sequenceXYZ = [copy.copy(nextXYZ)]
            sequenceE = [copy.copy(nextE)]
            if nextE > curE_p:
                sequenceExtruding = 1
            elif nextE < curE_p:
                sequenceExtruding = -1
            else:
                sequenceExtruding = 0
            newSequence = False

        with open(infname, 'r') as readfileobject, open(outfname, 'w') as outFile:
            for thisLine in readfileobject:
                if thisLine == '\n':
                    continue
                if not ((thisLine[0:3] == 'G0 ') or (thisLine[0:3] == 'G1 ')):
                    if not newSequence:
                        writeGcode(outFile, sequenceXYZ[-1], sequenceE[-1], sequenceFeedrate)
                    newSequence = True
                    outFile.write(thisLine)
                    if thisLine[0:3] == 'G92':
                        codes = thisLine.rstrip().split(' ')
                        for code in codes:
                            key = code[0]
                            idx = indices.get(key, 'default')
                            if idx == 2: curXYZ[0] = float(code[1:])
                            elif idx == 3: curXYZ[1] = float(code[1:])
                            elif idx == 4: curXYZ[2] = float(code[1:])
                            elif idx == 5: curE = float(code[1:])
                    continue

                codes = thisLine.split(';')[0].strip().split(' ')
                flags = [False]*6
                args = [0]*6
                for code in codes:
                    key = code[0]
                    idx = indices.get(key, 'default')
                    if idx != 'default':
                        flags[idx] = True
                        args[idx] = float(code[1:])

                if newSequence:
                    initSequence(flags, args, curXYZ, curE)
                else:
                    if flags[1] and args[1] != sequenceFeedrate:
                        writeGcode(outFile, sequenceXYZ[-1], sequenceE[-1], sequenceFeedrate)
                        initSequence(flags, args, curXYZ, curE)
                        continue
                    if flags[5]:
                        deltaE = args[5] - sequenceE[-1]
                        eDir = 1 if deltaE > 0 else (-1 if deltaE < 0 else 0)
                    else:
                        eDir = 0
                    if eDir != sequenceExtruding:
                        writeGcode(outFile, sequenceXYZ[-1], sequenceE[-1], sequenceFeedrate)
                        initSequence(flags, args, curXYZ, curE)
                        continue

                    nextXYZ = copy.deepcopy(sequenceXYZ[-1])
                    nextE = copy.deepcopy(sequenceE[-1])
                    if flags[2]: nextXYZ[0] = args[2]
                    if flags[3]: nextXYZ[1] = args[3]
                    if flags[4]: nextXYZ[2] = args[4]
                    if flags[5]: nextE = args[5]

                    # calculate trajectory error
                    error = 0
                    if len(sequenceXYZ) > 1:
                        pStart = sequenceXYZ[0]
                        pEnd = nextXYZ
                        pLine = [pEnd[i] - pStart[i] for i in range(3)]
                        lenLine = mag(pLine)
                        if lenLine > 0.0001:
                            for idx in range(1, len(sequenceXYZ)):
                                pCur = sequenceXYZ[idx]
                                pTarget = [pCur[i] - pStart[i] for i in range(3)]
                                d = mag(cross(pLine, pTarget)) / lenLine
                                if d > error:
                                    error = d

                    if error > ERRORTHRESH:
                        writeGcode(outFile, sequenceXYZ[-1], sequenceE[-1], sequenceFeedrate)
                        initSequence(flags, args, curXYZ, curE)
                    else:
                        sequenceXYZ.append(copy.copy(nextXYZ))
                        sequenceE.append(copy.copy(nextE))

            # Write remaining sequence
            if not newSequence:
                writeGcode(outFile, sequenceXYZ[-1], sequenceE[-1], sequenceFeedrate)

def adler32_checksum(fname):
    asum = 0
    f = open(fname, "rb")
    while True:
        data = f.read(256*1024*1024)
        if not data:
            break
        asum = adler32(data, asum)
        if asum < 0:
            asum += 2**32
    f.close()
    return asum

if __name__ == "__main__":
    root = tk.Tk()
    app = ModTApp(root)
    root.mainloop()

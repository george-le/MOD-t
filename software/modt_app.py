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
        self.root.title("MOD-t Printer Utility")
        self.root.geometry("760x620")
        self.root.minsize(680, 560)
        self.app_icon_photo = None

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
        self.configure_app_icon()
        self.create_widgets()

        # Start background polling thread
        self.poll_active = True
        self.poll_thread = threading.Thread(target=self.background_poll, daemon=True)
        self.poll_thread.start()

    def get_icon_directory(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        asset_root = os.path.join(base_dir, 'assets')

        platform_dirs = []
        if sys.platform == 'darwin':
            platform_dirs.extend([
                os.path.join(asset_root, 'macos'),
                os.path.join(asset_root, 'osx'),
            ])
        elif os.name == 'nt' or sys.platform.startswith('win'):
            platform_dirs.extend([
                os.path.join(asset_root, 'windows'),
                os.path.join(asset_root, 'win'),
            ])
        platform_dirs.append(asset_root)

        for icon_dir in platform_dirs:
            if os.path.isdir(icon_dir):
                return icon_dir
        return asset_root

    def configure_app_icon(self):
        icon_dir = self.get_icon_directory()
        candidates = [
            os.path.join(icon_dir, 'modt_app_icon.png'),
            os.path.join(icon_dir, 'modt_app_icon.ico'),
            os.path.join(icon_dir, 'modt_app_icon.icns'),
        ]

        for icon_path in candidates:
            if not os.path.exists(icon_path):
                continue
            try:
                if icon_path.lower().endswith('.png'):
                    image = tk.PhotoImage(file=icon_path)
                    self.root.iconphoto(True, image)
                    self.app_icon_photo = image
            except Exception:
                pass
            try:
                self.root.iconbitmap(default=icon_path)
            except Exception:
                pass
            break

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        bg = '#EEF4FF'
        panel = '#FFFFFF'
        panel_alt = '#F8FAFC'
        mute = '#64748B'
        text = '#0F172A'
        primary = '#2563EB'
        primary_dark = '#1D4ED8'
        success = '#0F766E'
        danger = '#DC2626'

        self.root.configure(bg=bg)
        style.configure('.', background=bg, foreground=text, font=('Arial', 10))
        style.configure('Card.TFrame', background=panel)
        style.configure('Panel.TFrame', background=panel_alt)
        style.configure('TLabel', background=bg, foreground=text)
        style.configure('Title.TLabel', font=('Arial', 22, 'bold'), foreground=primary, background=bg)
        style.configure('Section.TLabel', font=('Arial', 11, 'bold'), foreground=text, background=bg)
        style.configure('Muted.TLabel', font=('Arial', 9), foreground=mute, background=bg)
        style.configure('TButton', font=('Arial', 10, 'bold'), borderwidth=0, padding=(12, 10))
        style.configure('Primary.TButton', background=primary, foreground='white', padding=(14, 11), relief='flat')
        style.map('Primary.TButton', background=[('active', primary_dark)], foreground=[('active', 'white')])
        style.configure('Secondary.TButton', background='#E2E8F0', foreground=text, padding=(12, 10), relief='flat')
        style.map('Secondary.TButton', background=[('active', '#CBD5E1')], foreground=[('active', text)])
        style.configure('Ghost.TButton', background=panel, foreground=text, padding=(12, 10), relief='flat')
        style.map('Ghost.TButton', background=[('active', panel_alt)], foreground=[('active', text)])
        style.configure('TCheckbutton', background=bg, foreground=text)
        style.configure('Horizontal.TProgressbar', troughcolor='#E2E8F0', background=primary, thickness=10)
        style.configure('StatusChip.TLabel', background='#E2E8F0', foreground='#0F172A', font=('Arial', 9, 'bold'))

        self.theme_widgets = []

    def create_widgets(self):
        self.root.configure(bg='#EEF4FF')

        header_frame = tk.Frame(self.root, bg='#FFFFFF', bd=0, highlightthickness=1, highlightbackground='#DDE8F7', padx=20, pady=16)
        header_frame.pack(fill=tk.X, padx=18, pady=(18, 0))
        self.theme_widgets.append(header_frame)

        title_label = tk.Label(header_frame, text='MOD-t Operations', bg='#FFFFFF', fg='#1D4ED8', font=('Arial', 22, 'bold'))
        title_label.pack(side=tk.LEFT)
        self.theme_widgets.append(title_label)

        action_bar = tk.Frame(header_frame, bg='#FFFFFF')
        action_bar.pack(side=tk.RIGHT)
        self.theme_widgets.append(action_bar)

        self.conn_status_label = tk.Label(header_frame, text='● Disconnected', bg='#FFFFFF', fg='#DC2626', font=('Arial', 10, 'bold'))
        self.conn_status_label.pack(side=tk.RIGHT, padx=(0, 12))
        self.theme_widgets.append(self.conn_status_label)

        main_frame = tk.Frame(self.root, bg='#EEF4FF', padx=18, pady=18)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.theme_widgets.append(main_frame)

        left_frame = tk.Frame(main_frame, bg='#FFFFFF', bd=0, highlightthickness=1, highlightbackground='#DDE8F7', padx=14, pady=14)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        self.theme_widgets.append(left_frame)

        telemetry_header = tk.Label(left_frame, text='Telemetry', bg='#FFFFFF', fg='#0F172A', font=('Arial', 11, 'bold'))
        telemetry_header.pack(anchor=tk.W, pady=(0, 8))
        self.theme_widgets.append(telemetry_header)

        telemetry_grid = tk.Frame(left_frame, bg='#F8FAFC', padx=12, pady=12)
        telemetry_grid.pack(fill=tk.X)
        self.theme_widgets.append(telemetry_grid)

        self.lbl_temp = tk.Label(telemetry_grid, text='Hotend Temp: -- °C', bg='#E0F2FE', fg='#075985', font=('Arial', 11, 'bold'), padx=10, pady=8)
        self.lbl_temp.pack(fill=tk.X, pady=(0, 6))
        self.lbl_state = tk.Label(telemetry_grid, text='Printer State: --', bg='#ECFDF5', fg='#065F46', font=('Arial', 10, 'bold'), padx=10, pady=8)
        self.lbl_state.pack(fill=tk.X, pady=(0, 6))
        self.lbl_x = tk.Label(telemetry_grid, text='X Position: -- mm', bg='#F8FAFC', fg='#0F172A', padx=10, pady=8)
        self.lbl_x.pack(fill=tk.X, pady=(0, 6))
        self.lbl_y = tk.Label(telemetry_grid, text='Y Position: -- mm', bg='#F8FAFC', fg='#0F172A', padx=10, pady=8)
        self.lbl_y.pack(fill=tk.X, pady=(0, 6))
        self.lbl_z = tk.Label(telemetry_grid, text='Z Position: -- mm', bg='#F8FAFC', fg='#0F172A', padx=10, pady=8)
        self.lbl_z.pack(fill=tk.X, pady=(0, 0))
        for widget in [self.lbl_temp, self.lbl_state, self.lbl_x, self.lbl_y, self.lbl_z]:
            self.theme_widgets.append(widget)

        raw_header = tk.Label(left_frame, text='Raw Response Details', bg='#FFFFFF', fg='#0F172A', font=('Arial', 11, 'bold'))
        raw_header.pack(anchor=tk.W, pady=(14, 8))
        self.theme_widgets.append(raw_header)

        self.txt_telemetry = tk.Text(left_frame, height=14, width=36, font=('Courier', 9), bg='#F8FAFC', fg='#0F172A', wrap=tk.WORD, relief=tk.FLAT, borderwidth=1, highlightthickness=1, highlightbackground='#DDE8F7')
        self.txt_telemetry.pack(fill=tk.BOTH, expand=True)
        self.txt_telemetry.insert(tk.END, 'Waiting for connection...')
        self.txt_telemetry.config(state=tk.DISABLED)
        self.theme_widgets.append(self.txt_telemetry)

        right_frame = tk.Frame(main_frame, bg='#EEF4FF')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.theme_widgets.append(right_frame)

        fil_frame = tk.Frame(right_frame, bg='#FFFFFF', bd=0, highlightthickness=1, highlightbackground='#DDE8F7', padx=12, pady=12)
        fil_frame.pack(fill=tk.X, pady=(0, 10))
        self.theme_widgets.append(fil_frame)
        tk.Label(fil_frame, text='Filament', bg='#FFFFFF', fg='#0F172A', font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 8))
        self.btn_load = ttk.Button(fil_frame, text='Load Filament (210°C)', style='Secondary.TButton', command=self.load_filament)
        self.btn_load.pack(fill=tk.X, pady=3)
        self.btn_unload = ttk.Button(fil_frame, text='Unload Filament', style='Secondary.TButton', command=self.unload_filament)
        self.btn_unload.pack(fill=tk.X, pady=3)

        job_frame = tk.Frame(right_frame, bg='#FFFFFF', bd=0, highlightthickness=1, highlightbackground='#DDE8F7', padx=12, pady=12)
        job_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.theme_widgets.append(job_frame)
        tk.Label(job_frame, text='Print Job', bg='#FFFFFF', fg='#0F172A', font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 8))

        self.btn_select_file = ttk.Button(job_frame, text='Select G-Code File', style='Primary.TButton', command=self.select_file)
        self.btn_select_file.pack(fill=tk.X, pady=(0, 8))

        file_card = tk.Frame(job_frame, bg='#F8FAFC', bd=1, highlightthickness=1, highlightbackground='#DDE8F7', padx=10, pady=8)
        file_card.pack(fill=tk.X, pady=(0, 8))
        self.theme_widgets.append(file_card)
        tk.Label(file_card, text='Selected file', bg='#F8FAFC', fg='#475569', font=('Arial', 8, 'bold')).pack(anchor=tk.W)
        self.selected_file_label = tk.Label(file_card, text='No file selected', bg='#F8FAFC', fg='#0F172A', font=('Arial', 9), wraplength=260, justify=tk.LEFT)
        self.selected_file_label.pack(anchor=tk.W, pady=(2, 0))
        self.theme_widgets.append(self.selected_file_label)

        self.optimize_var = tk.BooleanVar(value=True)
        self.chk_optimize = ttk.Checkbutton(job_frame, text='Optimize G-code on the fly', variable=self.optimize_var)
        self.chk_optimize.pack(anchor=tk.W, pady=(0, 8))

        self.btn_print = ttk.Button(job_frame, text='Send to Printer', style='Primary.TButton', command=self.start_print)
        self.btn_print.pack(fill=tk.X, pady=(0, 6))
        self.btn_stop = ttk.Button(job_frame, text='Cancel Send/Job', style='Secondary.TButton', command=self.stop_print, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ttk.Progressbar(job_frame, orient='horizontal', mode='determinate', length=300, style='Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))
        self.progress_label = tk.Label(job_frame, text='Progress: 0.0%', bg='#FFFFFF', fg='#0F172A', font=('Arial', 9, 'bold'))
        self.progress_label.pack(anchor=tk.CENTER)
        self.eta_label = tk.Label(job_frame, text='Upload ETA: --', bg='#FFFFFF', fg='#475569', font=('Arial', 9, 'italic'))
        self.eta_label.pack(anchor=tk.CENTER, pady=(0, 4))

        self.trigger_label = tk.Label(job_frame, text='Waiting for print trigger', bg='#F8FAFC', fg='#475569', font=('Arial', 9, 'italic'), padx=10, pady=8)
        self.trigger_label.pack(fill=tk.X, pady=(6, 0))
        self.trigger_label.pack_forget()

        self.transfer_status = tk.Label(job_frame, text='Idle', bg='#F8FAFC', fg='#475569', font=('Arial', 9, 'bold'), padx=10, pady=8)
        self.transfer_status.pack(fill=tk.X, pady=(0, 6))
        self.transfer_status.pack_forget()

        self.print_eta_label = tk.Label(job_frame, text='Print ETA: unavailable', bg='#FFFFFF', fg='#475569', font=('Arial', 9, 'italic'))
        self.print_eta_label.pack(anchor=tk.CENTER, pady=(0, 4))
        self.print_eta_label.pack_forget()

        self.clear_nozzle_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'clearnozzle.gcode'))
        self.btn_clear_nozzle = ttk.Button(job_frame, text='Load bundled clearnozzle.gcode', style='Ghost.TButton', command=self.load_clear_nozzle_file)
        self.btn_clear_nozzle.pack(fill=tk.X, pady=(12, 0))

        self.btn_reset = ttk.Button(job_frame, text='Reset USB Connection', style='Ghost.TButton', command=self.reset_connection)
        self.btn_reset.pack(fill=tk.X, pady=(8, 0))

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

    def _first_matching_value(self, obj, keys):
        if isinstance(obj, dict):
            for key in keys:
                if key in obj and obj[key] is not None:
                    return obj[key]
            for value in obj.values():
                found = self._first_matching_value(value, keys)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = self._first_matching_value(item, keys)
                if found is not None:
                    return found
        return None

    def _normalize_temperature(self, value):
        if value is None or value == "--":
            return "--"
        if isinstance(value, dict):
            value = value.get('current', value.get('value', value.get('temp', value.get('celsius', value.get('actual', "--")))))
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        try:
            numeric = float(value)
            return int(numeric) if abs(numeric - round(numeric)) < 1e-6 else round(numeric, 1)
        except (TypeError, ValueError):
            return value

    def _extract_temperature_value(self, payload):
        if payload is None:
            return None
        if isinstance(payload, dict):
            for key in ['temperature', 'temp', 'hotend_temp', 'current_temp', 'actual_temp', 'heater_temp', 'extruder_temp', 'hotend', 'extruder']:
                if key in payload:
                    return payload[key]
            for key, value in payload.items():
                normalized = str(key).lower()
                if 'temp' in normalized or 'heater' in normalized or 'hotend' in normalized or 'extruder' in normalized:
                    if isinstance(value, (int, float)):
                        return value
                    if isinstance(value, dict):
                        nested = self._extract_temperature_value(value)
                        if nested is not None:
                            return nested
                nested = self._extract_temperature_value(value)
                if nested is not None:
                    return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self._extract_temperature_value(item)
                if nested is not None:
                    return nested
        return None

    def extract_status_state(self, payload):
        if payload is None:
            return None
        if isinstance(payload, dict):
            for key in ['state', 'printer_state', 'status_state', 'job_state']:
                value = payload.get(key)
                if value is not None:
                    return value
            for value in payload.values():
                nested = self.extract_status_state(value)
                if nested is not None:
                    return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self.extract_status_state(item)
                if nested is not None:
                    return nested
        return None

    def _parse_json_payload(self, raw_str):
        if raw_str is None:
            return None
        cleaned = raw_str.replace('\x00', '').strip()
        if not cleaned:
            return None
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if 0 <= start < end:
            try:
                return json.loads(cleaned[start:end+1])
            except Exception:
                pass
        return None

    def request_status(self):
        if not self.connected or not self.dev:
            return
        try:
            self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
            data = self.read_modt_response(0x83)
            if data:
                self.parse_status(data)
        except Exception:
            pass

    def parse_status(self, raw_str):
        try:
            decoded = self._parse_json_payload(raw_str)
            if not isinstance(decoded, dict):
                return
            self.status_data = decoded

            status = decoded.get("status")
            if status is None and isinstance(decoded.get("data"), dict):
                status = decoded.get("data").get("status")
            if status is None and isinstance(decoded.get("result"), dict):
                status = decoded.get("result").get("status")
            if status is None:
                status = decoded

            temp = self._normalize_temperature(self._extract_temperature_value(decoded))
            if temp == "--":
                temp = self._normalize_temperature(self._first_matching_value(status, ['temperature', 'temp', 'hotend_temp', 'current_temp', 'actual_temp', 'heater_temp', 'extruder_temp']))
            state = self.extract_status_state(decoded)
            if state is None:
                state = self._first_matching_value(status, ['state', 'printer_state', 'status_state'])

            pos = status.get('position') if isinstance(status, dict) else {}
            if pos is None:
                pos = {}
            if not isinstance(pos, dict):
                pos = {}
            x = pos.get('x', self._first_matching_value(status, ['x', 'x_pos', 'position_x']))
            y = pos.get('y', self._first_matching_value(status, ['y', 'y_pos', 'position_y']))
            z = pos.get('z', self._first_matching_value(status, ['z', 'z_pos', 'position_z']))

            # Update labels safely in Tkinter main thread
            self.root.after(0, lambda: self.update_telemetry_labels(temp, state, x, y, z, raw_str))
        except Exception:
            pass

    def humanize_status(self, state):
        if not state:
            return 'Unknown'
        mapping = {
            'STATE_IDLE': 'Idle',
            'STATE_BUSY': 'Busy',
            'STATE_PRINTING': 'Printing',
            'STATE_JOB_QUEUED': 'Queued',
            'STATE_JOB_PAUSED': 'Paused',
            'STATE_FILE_RX': 'Receiving file',
            'STATE_HEATING': 'Heating',
            'STATE_PREHEAT': 'Preheating',
            'STATE_ERROR': 'Error',
            'STATE_OFFLINE': 'Offline',
        }
        return mapping.get(state.upper(), state)

    def update_telemetry_labels(self, temp, state, x, y, z, raw_json):
        readable_state = self.humanize_status(state)
        self.lbl_temp.config(text=f"Hotend Temp: {temp} °C")
        self.lbl_state.config(text=f"Printer State: {readable_state}", fg='#065F46', bg='#ECFDF5')
        self.lbl_x.config(text=f"X Position: {x} mm")
        self.lbl_y.config(text=f"Y Position: {y} mm")
        self.lbl_z.config(text=f"Z Position: {z} mm")

        if readable_state == 'Receiving file':
            self.transfer_status.config(text='Transfer status: Receiving file', fg='#7C2D12', bg='#FEF3C7')
            self.transfer_status.pack(fill=tk.X, pady=(0, 6))
            self.trigger_label.config(text='Waiting for print trigger: press the MOD-t front button', fg='#7C2D12', bg='#FEF3C7')
            self.trigger_label.pack(fill=tk.X, pady=(6, 0))
        elif readable_state == 'Queued':
            self.transfer_status.config(text='Transfer status: Queued', fg='#065F46', bg='#ECFDF5')
            self.transfer_status.pack(fill=tk.X, pady=(0, 6))
            self.trigger_label.config(text='Ready: press the MOD-t front button to begin', fg='#065F46', bg='#ECFDF5')
            self.trigger_label.pack(fill=tk.X, pady=(6, 0))
        elif readable_state == 'Printing':
            self.transfer_status.config(text='Transfer status: Printing', fg='#0F172A', bg='#DBEAFE')
            self.transfer_status.pack(fill=tk.X, pady=(0, 6))
            self.trigger_label.pack_forget()
        else:
            self.transfer_status.pack_forget()
            self.trigger_label.pack_forget()

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

    def apply_theme(self):
        style = ttk.Style()
        style.configure('Primary.TButton', background='#2563EB', foreground='white', padding=(14, 11), relief='flat')
        style.map('Primary.TButton', background=[('active', '#1D4ED8')], foreground=[('active', 'white')])
        style.configure('Secondary.TButton', background='#E2E8F0', foreground='#0F172A', padding=(12, 10), relief='flat')
        style.map('Secondary.TButton', background=[('active', '#CBD5E1')], foreground=[('active', '#0F172A')])
        style.configure('Ghost.TButton', background='#FFFFFF', foreground='#0F172A', padding=(12, 10), relief='flat')
        style.map('Ghost.TButton', background=[('active', '#F8FAFC')], foreground=[('active', '#0F172A')])

        self.root.configure(bg='#EEF4FF')
        self.conn_status_label.config(bg='#FFFFFF', fg='#DC2626')
        self.lbl_temp.config(bg='#E0F2FE', fg='#075985')
        self.lbl_state.config(bg='#ECFDF5', fg='#065F46')
        self.lbl_x.config(bg='#F8FAFC', fg='#0F172A')
        self.lbl_y.config(bg='#F8FAFC', fg='#0F172A')
        self.lbl_z.config(bg='#F8FAFC', fg='#0F172A')
        self.txt_telemetry.configure(bg='#F8FAFC', fg='#0F172A')
        self.progress_label.configure(bg='#FFFFFF', fg='#0F172A')
        self.eta_label.configure(bg='#FFFFFF', fg='#475569')
        self.print_eta_label.configure(bg='#FFFFFF', fg='#475569')
        self.selected_file_label.configure(bg='#F8FAFC', fg='#0F172A')
        self.transfer_status.configure(bg='#F8FAFC', fg='#475569')
        self.trigger_label.configure(bg='#F8FAFC', fg='#475569')

        for widget in self.theme_widgets:
            try:
                widget.configure(bg='#FFFFFF')
            except Exception:
                pass
            try:
                if isinstance(widget, tk.Label):
                    widget.configure(fg='#0F172A')
            except Exception:
                pass

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
            self.root.after(0, lambda: self.update_log("Filament load command sent. Requesting fresh status..."))
            self.request_status()
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
            self.root.after(0, lambda: self.update_log("Filament unload command sent. Requesting fresh status..."))
            self.request_status()
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
        self.progress_label.config(text="Preparing file transfer...")
        self.root.after(0, lambda: messagebox.showinfo(
            "Transfer in progress",
            "Sending the G-code file to the MOD-t. Keep the USB connected and wait until the printer finishes receiving the file. When upload is complete, press the front button on the printer to start printing."
        ))

        self.stop_print_flag = False
        self.transfer_started_at = time.monotonic()
        self.print_thread = threading.Thread(target=self.print_worker, args=(fname,), daemon=True)
        self.print_thread.start()

    def stop_print(self):
        self.stop_print_flag = True
        self.btn_stop.config(state=tk.DISABLED)

    def reset_connection(self):
        self.stop_print_flag = True
        self.connected = False
        self.dev = None
        self.root.after(0, self.update_status_ui_disconnected)
        messagebox.showinfo("Reset", "USB connection state cleared. The app will reconnect automatically if the printer is present.")

    def show_optimization_warning(self, error_text):
        messagebox.showwarning("Warning", f"G-code optimization failed, sending original file. Error: {error_text}")

    def wait_for_ready_state(self, timeout_seconds=45.0):
        deadline = time.monotonic() + timeout_seconds
        last_state = None
        while time.monotonic() < deadline:
            if self.stop_print_flag:
                return False
            try:
                self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
                data = self.read_modt_response(0x83)
                if data:
                    self.parse_status(data)
                    state = self.extract_status_state(self.status_data)
                    normalized = str(state).upper() if state else ''
                    last_state = normalized
                    if normalized in ('STATE_JOB_QUEUED', 'STATE_IDLE', 'STATE_PRINTING', 'STATE_HEATING'):
                        return True
                    if normalized == 'STATE_FILE_RX':
                        self.root.after(0, lambda: self.progress_label.config(text='Transfer complete — waiting for printer trigger'))
            except Exception:
                pass
            time.sleep(0.5)

        # A MOD-t that is still blinking after the file transfer is normal; it is waiting for the
        # physical front-button trigger. Do not force this into a false "ready" state.
        if last_state == 'STATE_FILE_RX':
            return False
        return False

    def print_worker(self, fname):
        # 1. Optimize G-code if checked
        if self.optimize_var.get():
            self.root.after(0, lambda: self.progress_label.config(text="Optimizing G-code..."))
            opt_filename = fname.replace(".gcode", "_optimized.gcode")
            try:
                self.run_gcode_optimization(fname, opt_filename)
                fname_to_send = opt_filename
            except Exception as e:
                error_text = str(e)
                self.root.after(0, lambda msg=error_text: self.show_optimization_warning(msg))
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
                ready = self.wait_for_ready_state()
                final_state = self.extract_status_state(self.status_data) if self.status_data else None
                final_state_display = str(final_state).upper() if final_state else 'UNKNOWN'

                if ready:
                    self.root.after(0, lambda: self.progress_label.config(text='Ready — press the printer button'))
                    self.root.after(0, lambda: self.print_eta_label.config(text='Print ETA: unavailable'))
                    self.root.after(0, lambda: self.print_eta_label.pack(anchor=tk.CENTER, pady=(0, 4)))
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Ready to print",
                        "The MOD-t reported a ready/queued state. Press the front button on the printer to begin printing."
                    ))
                elif final_state_display == 'STATE_FILE_RX':
                    self.root.after(0, lambda: self.progress_label.config(text='File received — waiting for print trigger'))
                    self.root.after(0, lambda: self.print_eta_label.config(text='Print ETA: unavailable'))
                    self.root.after(0, lambda: self.print_eta_label.pack(anchor=tk.CENTER, pady=(0, 4)))
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Transfer complete",
                        "The file was received by the MOD-t and the printer is blinking while waiting for the front button trigger. Press the button on the printer to start the print."
                    ))
                else:
                    self.root.after(0, lambda: self.progress_label.config(text='Transfer finished — waiting for printer state'))
                    self.root.after(0, lambda: self.print_eta_label.config(text='Print ETA: unavailable'))
                    self.root.after(0, lambda: self.print_eta_label.pack(anchor=tk.CENTER, pady=(0, 4)))
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Printer not ready",
                        "The file transfer finished, but the MOD-t has not reached a queued/ready state. Keep the USB connected and be ready to press the printer button when it stops blinking."
                    ))

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

        if val > 0 and self.transfer_started_at is not None:
            elapsed = max(time.monotonic() - self.transfer_started_at, 0.1)
            eta_seconds = elapsed * (100.0 - val) / max(val, 0.1)
            minutes, seconds = divmod(int(eta_seconds), 60)
            if minutes > 0:
                eta_text = f"Upload ETA: {minutes}m {seconds}s"
            else:
                eta_text = f"Upload ETA: {seconds}s"
        else:
            eta_text = "Upload ETA: --"
        self.eta_label.config(text=eta_text)

    def reset_print_ui(self):
        self.btn_print.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_select_file.config(state=tk.NORMAL)
        self.chk_optimize.config(state=tk.NORMAL)
        self.eta_label.config(text='Upload ETA: --')
        self.print_eta_label.config(text='Print ETA: unavailable')
        self.print_eta_label.pack_forget()

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

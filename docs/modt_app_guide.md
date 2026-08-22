# MOD-t Desktop Utility Guide

This guide explains what the desktop utility in `software/modt_app.py` does and how to run or package it on macOS and Windows.

## What the app does

`software/modt_app.py` is a Tkinter-based desktop utility for interacting with the MOD-t printer over USB. It is designed for a real hardware workflow, not a simulated printer.

Key capabilities include:

- Connect to the MOD-t over USB using `pyusb`
- Poll the printer status and show raw status JSON and human-readable telemetry
- Display hotend temperature, printer state, and movement values
- Send a G-code file to the printer
- Show transfer progress and upload ETA
- Pause/cancel the transfer if needed
- Offer helper actions such as filament load/unload and a bundled `clearnozzle.gcode` helper
- Explain the physical front-button workflow: after upload completes, the user usually needs to press the printer button to start the print

The app intentionally keeps raw response data visible so the operator can inspect the MOD-t status stream while they work.

## Project layout

Relevant files:

- `software/modt_app.py` — main desktop app
- `clearnozzle.gcode` — bundled nozzle-clear helper G-code
- `MOD-t_Printer_Utility.spec` — PyInstaller spec used for packaging on macOS
- `scripts/send_gcode.py` — useful protocol reference for upload flow and status handling

## Requirements

Python requirements:

- Python 3.10+ recommended
- `tkinter` (bundled with Python on most installs)
- `pyusb`
- `PyInstaller` for packaging an app bundle or executable

USB requirements:

- The MOD-t must be connected by USB
- On macOS, `libusb` via Homebrew is typically required
- On Windows, a libusb-compatible driver (often installed via Zadig) may be required for the printer to show up correctly

## Running from source

From the repo root:

```bash
cd /path/to/MOD-t
python3 -m venv .venv
source .venv/bin/activate
pip install pyusb pyinstaller
python3 software/modt_app.py
```

On Windows PowerShell:

```powershell
cd C:\path\to\MOD-t
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pyusb pyinstaller
python .\software\modt_app.py
```

If Python cannot find `tkinter`, install the standard Python package for your OS or use a full Python distribution that includes Tk.

## macOS build

This repo already contains a PyInstaller spec file: `MOD-t_Printer_Utility.spec`.

### Install dependencies

```bash
cd /path/to/MOD-t
python3 -m venv .venv
source .venv/bin/activate
pip install pyusb pyinstaller
```

### Ensure libusb is available

Apple Silicon / modern macOS (Homebrew):

```bash
brew install libusb
```

The existing spec references:

```python
('/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib', '.')
```

If your Homebrew install uses Intel paths instead, adjust the file path accordingly, for example:

```bash
/usr/local/opt/libusb/lib/libusb-1.0.dylib
```

### Build

```bash
pyinstaller MOD-t_Printer_Utility.spec
```

This produces an app bundle in the `dist/` folder, typically:

```text
dist/MOD-t_Printer_Utility.app
```

### Notes for macOS packaging

- The app uses the files in the repo relative to the script path; when packaging, make sure the `clearnozzle.gcode` helper is included in the app bundle or the app is launched from a folder where it can still resolve the file.
- If the app fails to connect to the printer after packaging, re-check the `libusb` location and confirm the printer is recognized by macOS in the system USB listing.

## Windows build

Windows packaging is similar, but you should expect to install a libusb-compatible driver before the app can communicate with the MOD-t device.

### Install dependencies

```powershell
cd C:\path\to\MOD-t
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pyusb pyinstaller
```

### Install the USB driver

On Windows, a typical fix is to install a libusb-compatible driver using Zadig:

1. Plug in the MOD-t over USB
2. Launch Zadig
3. Select the MOD-t USB device
4. Replace the driver with `WinUSB` or `libusbK`

This is often required for `pyusb` to access the device reliably.

### Build the executable

```powershell
pyinstaller --windowed --name MOD-t_Printer_Utility --add-data "clearnozzle.gcode;." software\modt_app.py
```

This creates a Windows app in the `dist` directory.

If you want a more conservative packaging flow, you can also use the same application entry point as the script directly:

```powershell
python .\software\modt_app.py
```

## Build tips and common issues

### `No printer connected`

- Check the USB cable and port
- Confirm the MOD-t appears in the OS device list
- Confirm `pyusb` can enumerate devices
- On Windows, make sure the correct libusb-compatible driver is installed

### `libusb` missing

- Install `libusb` via Homebrew on macOS
- On Windows, use libusb-compatible drivers and ensure `libusb` is installed for Python via `pyusb`

### `clearnozzle.gcode` not found

The app expects the clear-nozzle helper to be available relative to the project. If the packaged app is moved, confirm the data file is included in the build output.

### Print start flow

The MOD-t’s workflow is not fully auto-starting from the app. The app warns users to press the front button on the printer after the upload completes. This is intentional and matches the known device behavior.

## Recommended workflow

1. Connect the MOD-t via USB
2. Launch the app
3. Confirm the printer is connected and the telemetry starts updating
4. Load a G-code file or the `clearnozzle.gcode` helper
5. Start the transfer
6. Wait for the app to report the printer is queued/ready
7. Press the printer’s front button to begin the print

## Summary

`modt_app.py` is a practical desktop utility for the MOD-t designed around real hardware behavior, with a strong emphasis on:

- hardware status visibility
- raw telemetry inspection
- controlled file transfer
- clearer printer actions
- helper utilities like clearing the nozzle

It is designed to be run directly from the repo during development and packaged into a desktop app for macOS and Windows when you want a more polished release build.

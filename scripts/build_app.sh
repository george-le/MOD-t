#!/bin/bash
set -e

# Change directory to the workspace root
cd "$(dirname "$0")/.."

echo "============================================="
echo "Building Standalone MOD-t Printer Utility App"
echo "============================================="

# Ensure virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv .venv
    .venv/bin/pip install pyusb pyinstaller
fi

# Run PyInstaller
echo "Compiling with PyInstaller..."

# Try to locate libusb installed by Homebrew and include it in the app bundle so
# the packaged application has a native libusb backend available for PyUSB.
LIBUSB_ADD_BINARY=""
if command -v brew >/dev/null 2>&1; then
    BREW_PREFIX=$(brew --prefix libusb 2>/dev/null || true)
    if [ -n "$BREW_PREFIX" ]; then
        LIBUSB_DYLIB="$BREW_PREFIX/lib/libusb-1.0.dylib"
        if [ -f "$LIBUSB_DYLIB" ]; then
            LIBUSB_ADD_BINARY="--add-binary '$LIBUSB_DYLIB:.'"
            echo "Including libusb from: $LIBUSB_DYLIB"
        fi
    fi
fi

if [ -z "$LIBUSB_ADD_BINARY" ]; then
    echo "Warning: libusb dylib not found via Homebrew. Packaged app may not detect USB devices."
    .venv/bin/pyinstaller --windowed --noconfirm --clean --name="MOD-t_Printer_Utility" software/modt_app.py
else
    # Use eval so the constructed --add-binary argument is expanded correctly.
    eval ".venv/bin/pyinstaller --windowed --noconfirm --clean --name=\"MOD-t_Printer_Utility\" $LIBUSB_ADD_BINARY software/modt_app.py"
fi

echo "============================================="
echo "Build complete!"
echo "Standalone application bundle generated at:"
echo "dist/MOD-t_Printer_Utility.app"
echo "============================================="

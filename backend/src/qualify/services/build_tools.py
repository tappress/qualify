"""Resolve paths to bundled external binaries (nixpacks, etc.).

In a frozen PyInstaller binary, external binaries are extracted to sys._MEIPASS.
In dev mode they must be on PATH.
"""
import os
import sys


def nixpacks_bin() -> str:
    if getattr(sys, "frozen", False):
        name = "nixpacks.exe" if sys.platform == "win32" else "nixpacks"
        return os.path.join(sys._MEIPASS, name)
    return "nixpacks"

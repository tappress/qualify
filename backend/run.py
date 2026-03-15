"""
PyInstaller entry point and direct run script.
Use this instead of `uvicorn app.main:app` so the frozen binary
can pass the app object directly (string imports don't work when frozen).
"""
import os
import subprocess
import sys
import asyncio
import threading
import time
import webbrowser

# Windows requires ProactorEventLoop for subprocess support (docker build, git, etc.)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from qualify.cli import main as cli_main
from qualify.main import app
from qualify.services.auth import get_token

PORT = int(os.environ.get("QUALIFY_PORT", 65432))

_CLI_COMMANDS = {"link", "deploy"}


def _is_wsl() -> bool:
    try:
        return "microsoft" in open("/proc/version").read().lower()
    except OSError:
        return False


def _open_browser() -> None:
    time.sleep(1.5)
    url = f"http://localhost:{PORT}/?token={get_token()}"
    if _is_wsl():
        # Open in the Windows host browser; powershell avoids cmd.exe UNC path noise
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f'Start-Process "{url}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in _CLI_COMMANDS:
        cli_main()
    else:
        print(f"Qualify is running at http://localhost:{PORT}")
        print("Press Ctrl+C to stop.")
        threading.Thread(target=_open_browser, daemon=True).start()
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

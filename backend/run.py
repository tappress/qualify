"""
PyInstaller entry point and direct run script.
Use this instead of `uvicorn app.main:app` so the frozen binary
can pass the app object directly (string imports don't work when frozen).
"""
import os
import sys
import asyncio
import threading
import webbrowser

# Windows requires ProactorEventLoop for subprocess support (docker build, git, etc.)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from qualify.main import app

PORT = int(os.environ.get("QUALIFY_PORT", 65432))


def _is_wsl() -> bool:
    try:
        return "microsoft" in open("/proc/version").read().lower()
    except OSError:
        return False


def _open_browser() -> None:
    import time
    time.sleep(1.5)
    url = f"http://localhost:{PORT}"
    if _is_wsl():
        # Open in the Windows host browser; powershell avoids cmd.exe UNC path noise
        import subprocess
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f'Start-Process "{url}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    print(f"Qualify is running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

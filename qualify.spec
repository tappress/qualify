# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Qualify.
Build from the project root:
    pyinstaller qualify.spec
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Bundle the platform-specific nixpacks binary if it was downloaded during build
_nixpacks_name = "nixpacks.exe" if sys.platform == "win32" else "nixpacks"
_nixpacks_path = BACKEND / _nixpacks_name
_nixpacks_binaries = [(str(_nixpacks_path), ".")] if _nixpacks_path.exists() else []

a = Analysis(
    [str(BACKEND / "run.py")],
    pathex=[str(BACKEND), str(BACKEND / "src")],
    binaries=_nixpacks_binaries,
    datas=[
        # Bundle the built frontend into the binary
        (str(FRONTEND_DIST), "frontend/dist"),
    ],
    hiddenimports=[
        # uvicorn internals
        "uvicorn.main",
        "uvicorn.config",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.logging",
        # fastapi / starlette
        "fastapi",
        "fastapi.staticfiles",
        "fastapi.responses",
        "starlette.staticfiles",
        "starlette.routing",
        # pydantic
        "pydantic",
        "pydantic.v1",
        # asyncssh
        "asyncssh",
        "asyncssh.crypto",
        # keyring backends
        "keyring",
        "keyring.backends.SecretService",
        "keyring.backends.macOS",
        "keyring.backends.Windows",
        "keyring.backends.fail",
        "keyring.backends.null",
        # misc
        "yaml",
        "aiofiles",
        "uuid_utils",
        "cryptography",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.backends.openssl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="qualify",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # keep console so users can see startup message / errors
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

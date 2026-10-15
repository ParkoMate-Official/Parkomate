# PyInstaller spec - one folder "dist\ParkomateStation" with two programs:
#
#   ParkomateStation.exe   the station (no console window)
#   parkomate.exe          the same program for the command line: admin create, doctor,
#                          measuring-device, secrets set, flash, report ...
#
# Build:  uv run --group build pyinstaller packaging\parkomate.spec --noconfirm
# (packaging\build.ps1 does this and then makes the Setup.exe.)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

HERE = Path(SPECPATH)
ROOT = HERE.parent
ICON = HERE / "parkomate.ico"

datas = []
datas += collect_data_files("parkomate")  # i18n JSON, SQL migrations, fonts, icons
datas += collect_data_files("esptool")  # the flasher stubs esptool uploads to the chip
binaries = collect_dynamic_libs("pyzbar")  # libzbar-64.dll + libiconv.dll (QR decoding)
hiddenimports = [
    *collect_submodules("parkomate"),
    *collect_submodules("keyring.backends"),  # Windows Credential Manager backend
    *collect_submodules("esptool"),
    "serial.tools.list_ports_windows",
]

a = Analysis(
    [str(HERE / "launch.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "PySide6.QtWebEngineCore"],
    noarchive=False,
)
# Python's own OpenSSL must sit next to _ssl.pyd. A build started from Git Bash finds Git's
# MinGW libcrypto/libssl on PATH first ("DLL load failed while importing _ssl") - pin ours.
PYTHON_DLLS = Path(sys.base_prefix) / "DLLs"
PINNED = {"libcrypto-3-x64.dll", "libssl-3-x64.dll"}
a.binaries = [
    (dest, str(PYTHON_DLLS / Path(dest).name), kind)
    if Path(dest).name.lower() in PINNED and (PYTHON_DLLS / Path(dest).name).exists()
    else (dest, src, kind)
    for dest, src, kind in a.binaries
]

pyz = PYZ(a.pure)

common = dict(
    exclude_binaries=True,
    debug=False,
    strip=False,
    upx=False,
    icon=str(ICON) if ICON.exists() else None,
)
station = EXE(pyz, a.scripts, [], name="ParkomateStation", console=False, **common)
command_line = EXE(pyz, a.scripts, [], name="parkomate", console=True, **common)

coll = COLLECT(
    station,
    command_line,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ParkomateStation",
)

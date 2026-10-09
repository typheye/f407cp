# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

package_dir = Path(SPECPATH)
source_root = package_dir.parent
assets_dir = package_dir / "assets"

a = Analysis(
    [str(package_dir / "app.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=[(str(assets_dir / "favicon.ico"), "japkit/assets")],
    hiddenimports=[
        "PyQt5", "PyQt5.QtWidgets", "PyQt5.QtCore", "PyQt5.QtGui",
        "pyqtgraph", "pyqtgraph.opengl",
        "numpy", "cv2",
        # PyOpenGL selects its display backend at runtime, so PyInstaller cannot
        # see these imports. Without them the frozen app logs
        # "Unable to import OpenGL.platform.egl.EGLPlatform".
        *collect_submodules("OpenGL.platform"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Not imported by JAPKit at runtime; PyInstaller's static analysis still
    # follows an optional `try: import torchvision` branch in the environment and
    # would otherwise bundle ~2.6 GB of torch/CUDA libs.
    excludes=[
        "torch", "torchvision", "torchaudio", "ultralytics",
        "thop", "functorch", "nvidia", "sympy", "mpmath",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="JAPKit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

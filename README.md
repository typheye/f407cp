# F407CP PC Tools

Command-line host tools for the STM32F407 firmware, packaged as standalone
Windows executables with PyInstaller.

| Tool       | Description                                                        |
| ---------- | ------------------------------------------------------------------ |
| `tvidtool` | Convert a normal video into a `.tvid` stream for SD-card playback. |
| `sbltool`  | SBL FASTBOOT USB CDC flash protocol host.                          |
| `tdb`      | TOS Debug Bridge REC USB CDC host for filesystem/settings/diag.    |

## TVID Tool

Convert a normal video into a `.tvid` stream that the STM32F407 firmware can
play from SD card. The converter uses bundled OpenCV when packaged; it does not
require an external `ffmpeg.exe` in PATH.

```powershell
python src\tvidtool\app.py input.mp4 -o test.tvid --fps 60 --size 240x240
```

To export only converted frames 0 through 999 (the end frame is exclusive):

```powershell
python src\tvidtool\app.py input.mp4 -o test.tvid --fps 60 --size 240x240 --start-frame 0 --end-frame 1000
```

Copy the output to the SD card as:

```text
0:/storage/test.tvid
```

The board-side launcher will play it automatically when the file exists and is
valid.

Note: regenerate existing `.tvid` files with the current tool. The firmware fast
path expects LCD-ready big-endian RGB565 payloads.

## SBL Tool / TDB

Both tools talk to the board over USB CDC using `pyserial`. Run them from source
directly:

```powershell
python src\sbltool\app.py --help
python src\tdb\app.py --help
```

## Build

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1
```

This builds `tvidtool.exe`, `sbltool.exe` and `tdb.exe` into
`dist\platform-tools\`.

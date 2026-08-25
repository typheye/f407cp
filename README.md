# F407CP PC Tools

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

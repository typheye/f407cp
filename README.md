<div align="center">

# F407CP PC Tools (Windows)

**Windows 上位机工具 — tvidtool / sbltool / tdb**

[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)]()
[![Language](https://img.shields.io/badge/Language-Python-yellow.svg)]()
[![Packaging](https://img.shields.io/badge/Packaging-PyInstaller-lightgrey.svg)]()

</div>

---

## 概述

STM32F407 固件的 Windows 命令行上位机工具，使用 PyInstaller 打包为独立可执行文件（`dist\platform-tools\*.exe`）。

| 工具 | 版本 | 说明 |
|------|------|------|
| `tvidtool` | v0.1.0 | 将普通视频转换为 `.tvid` 流，供 SD 卡播放 |
| `sbltool` | v1.0.2 | SBL FASTBOOT USB CDC 烧录协议主机 (PID 0x5751) |
| `tdb` | v1.0.1 | TOS Debug Bridge REC USB CDC 主机，文件/设置/诊断 (PID 0x5756) |

---

## 环境

构建使用 `f407cp` Conda 环境。首次创建：

```powershell
conda env create -f environment.yml
# 或，在已有环境下：
python -m pip install -r requirement.txt
```

依赖：`pyinstaller`、`opencv-python`、`pyserial`。

---

## TVID Tool

将普通视频转换为 `.tvid` 流，固件可从 SD 卡播放。打包后使用内置 OpenCV，无需在 `PATH` 中额外提供 `ffmpeg.exe`。

```powershell
python src\tvidtool\app.py input.mp4 -o test.tvid --fps 60 --size 240x240
```

仅导出第 0 到 999 帧（结束帧不包含）：

```powershell
python src\tvidtool\app.py input.mp4 -o test.tvid --fps 60 --size 240x240 --start-frame 0 --end-frame 1000
```

将输出拷贝到 SD 卡：

```text
0:/storage/test.tvid
```

文件存在且有效时，从板启动器会自动播放。

> 注意：请用当前工具重新生成旧的 `.tvid` 文件。固件快速路径要求 LCD 就绪的大端 RGB565 载荷。

---

## SBL Tool

`sbltool` 通过 USB CDC 与设备 FASTBOOT 协议通信。运行方式：

```powershell
python src\sbltool\app.py --help
python src\sbltool\app.py examples
```

常用命令：

```powershell
# 设备探测
sbltool devices

# 读取变量 / 分区表
sbltool getvar all
sbltool partitions

# 烧录（sbl/rec 为分阶段，system 为直写）
sbltool --wait flash sbl C:\path\sbl.bin
sbltool --wait flash rec C:\path\rec.bin
sbltool flash system C:\path\system.bin

# 擦除
sbltool erase rec
sbltool erase system

# 重启
sbltool reboot
sbltool reboot recovery
sbltool reboot bootloader

# OEM 解锁 / 上锁（解锁会清除全部用户数据）
sbltool oem unlock
sbltool oem lock
```

---

## TDB

`tdb` 是 REC 模式下的调试桥（TOS Debug Bridge），提供设备 Shell 与文件传输。

```powershell
python src\tdb\app.py --help
```

常用命令：

```powershell
# 设备探测 / 连接 / 断开
tdb devices
tdb connect
tdb disconnect

# 交互式 Shell，或执行单条命令
tdb shell
tdb shell ls

# 文件推送 / 拉取
tdb push local.bin 0:/storage/local.bin
tdb pull 0:/storage/file.bin .\file.bin
```

连接参数：`-s/--serial`、`-b/--baud`、`--timeout`。

---

## 构建

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1
```

构建 `tvidtool.exe`、`sbltool.exe`、`tdb.exe` 到 `dist\platform-tools\`。脚本会在检测到 conda 时自动激活 `f407cp` 环境。

```powershell
# 构建并安装到当前 Conda 环境的 Scripts\
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -Install
```

## 清理

```powershell
scripts\clean.bat
```

---

## 项目结构

```text
win-pc/
├── src/                       # 源码
│   ├── tvidtool/              # 视频 → .tvid 转换
│   ├── sbltool/               # FASTBOOT 烧录主机
│   └── tdb/                   # 调试桥
├── scripts/                   # 构建 / 清理脚本
│   ├── build.ps1
│   └── clean.bat
├── environment.yml            # Conda 环境定义
├── requirement.txt            # pip 依赖
├── build/                     # 构建输出 (gitignored)
└── dist/                      # 产物 platform-tools (gitignored)
```

---

## 许可证

Copyright (c) 2021-2026 Typheye

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

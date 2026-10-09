<div align="center">

# JAPKit — JanPNP Desktop Debug Tool

**上位机调试工具 — 灰度检测 + 遥测监控 + 性能分析**

[![Platform](https://img.shields.io/badge/Platform-Linux-blue.svg)]()
[![Language](https://img.shields.io/badge/Language-Python_3.11-yellow.svg)]()
[![License](https://img.shields.io/badge/License-GPLv2-green.svg)]()

</div>

## 概述

JAPKit 是基于 PyQt5 的 Linux 桌面工具，通过 HTTP 与树莓派上的 JanPNP 服务通信，提供：

| 功能 | 说明 |
|------|------|
| **Gray Detection** | 摄像头图像分析、HSV/LAB 灰度检测 |
| **Telemetry** | 电机实时位置/速度图表、3D 运动轨迹 |
| **Performance** | 校准测试、FPS/Ping/CPU/Mem 监控 |

## 快速开始

### 前置条件

- Linux（GNOME / Wayland 或 X11）
- Miniconda 或 Anaconda（Python 3.11）

### 一键安装

```bash
cd ~/Code/janpnp/linux-pc
scripts/setup-conda.sh
```

自动完成：创建 `janpnp` Conda 环境 → 安装依赖 → 构建可执行文件。

### 分步构建

```bash
conda activate janpnp
python -m pip install -r requirement.txt
bash scripts/build.sh
```

### 运行

```bash
# 开发模式直接跑源码
conda activate janpnp
python src/japkit/app.py

# 或运行打包产物
dist/JAPKit
```

> **VSCode**：`Ctrl+Shift+B` → 选择 `Play` / `Build` / `Clean`。

### Linux 平台注意事项

这几条是移植过程中踩到的坑，换机器复现时先看这里：

**1. 依赖必须用 `opencv-python-headless`，不能用 `opencv-python`。**
后者自带一套 Qt 插件，并会在 import 时改写 `QT_QPA_PLATFORM_PLUGIN_PATH`（见
`cv2/config-3.py`），导致 PyQt5 的 `xcb` 平台插件加载失败：
`qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in ".../cv2/qt/plugins"`。
JAPKit 只用到 `cv2.imread` / `cv2.imwrite`，不涉及 cv2 的 GUI，headless 完全够用。

**2. 3D 页面需要 `PYOPENGL_PLATFORM` 与 Qt 后端对齐。**
PyOpenGL 与 Qt 在 Linux 上各自选 GL 后端：PyOpenGL 默认 EGL，而 PyQt5 在
`QT_QPA_PLATFORM` 未设置时默认 X11（xcb/GLX）。两者不一致时
`GetCurrentContext()` 返回 `None`，所有 GL 调用抛
`Attempt to retrieve context when no valid context`，3D 页面渲染成纯色。
`app.py` 顶部已自动对齐，无需手动设置。

**3. 新窗口不会像 Windows 那样自动置顶。**
X11/GNOME 要求显式 `raise_()` + `activateWindow()`，且受焦点窃取防护
（`focus-new-windows='smart'`）影响。所有 `showMaximized()` 之后都已补上这两句。

## 项目结构

```text
linux-pc/
├── src/
│   └── japkit/           # JAPKit source code
│       ├── app.py        # Main entry point
│       ├── japkit.spec   # PyInstaller configuration
│       ├── depends/      # Feature modules
│       └── assets/       # Icons
├── scripts/              # Build scripts
│   ├── build.sh          # PyInstaller build
│   ├── clean.sh          # Cleanup
│   └── setup-conda.sh    # One-step environment setup
├── docs/                 # Documentation
├── environment.yml       # Conda environment
├── requirement.txt       # pip dependencies
├── LICENSE               # GPLv2
└── README.md
```

## 文档

| 文档 | 说明 |
|------|------|
| [technical-docs.md](docs/technical-docs.md) | 架构、通信、特殊实现 |
| [style-docs.md](docs/style-docs.md) | 代码风格规范 |
| [update-docs.md](docs/update-docs.md) | 变更记录 |

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

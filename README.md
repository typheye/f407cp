<div align="center">

# F407CP — STM32F407 控制面板平台

**嵌入式物联网平台 · TOS 安全固件 + PC 工具（Windows / Linux）**

[![Platform](https://img.shields.io/badge/Platform-STM32F407-orange.svg)]()
[![Language](https://img.shields.io/badge/Language-C%2FC%2B%2B%20%7C%20Python-blue.svg)]()
[![Boot](https://img.shields.io/badge/Boot-ECDSA%20P%2B256%20Secure-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-GPLv2-green.svg)]()

</div>

---

## 概述

F407CP 是一个运行于 **STM32F407ZGT6** 上的嵌入式平台，固件内部沿用 **TOS（Typheye Operating System）**，采用 **ECDSA P-256 + SHA-256 安全启动**、**FASTMAP 5 分区**布局，提供 240×240 LCD 图形界面、SD 卡持久化、视频播放（`.tvid`）、传感器采集等功能。上位机 PC 工具（Windows / Linux）涵盖视频转换、FASTBOOT 烧录、调试桥接。

项目按目录组织为三个独立子仓库（均位于 `main` 分支）：

| 目录 | 说明 | 语言 |
|------|------|------|
| **[slave-board](slave-board/README.md)** | STM32F407 从板固件：安全启动链、GUI、驱动、文件系统 | C / C++ |
| **[win-pc](win-pc/README.md)** | Windows 上位机工具：tvidtool / sbltool / tdb | Python |
| **[linux-pc](linux-pc/README.md)** | Linux 上位机工具：tvidtool / sbltool / tdb | Python |

---

## 系统架构

### 三层结构

| 层 | 组件 | 职责 | 通信 |
|----|------|------|------|
| **主控** | `slave-board` · STM32F407ZGT6 | 安全启动、GUI、驱动、文件系统、视频播放 | USB CDC / USART1 |
| **上位机 (Windows)** | `win-pc` · Windows 工具 | tvidtool 视频转换、sbltool 烧录、tdb 调试桥 | USB CDC |
| **上位机 (Linux)** | `linux-pc` · Linux 工具 | tvidtool 视频转换、sbltool 烧录、tdb 调试桥 | USB CDC |

### slave-board 固件分区

| 分区 | 大小 | 功能 | 安全 |
|------|------|------|------|
| **ELF** | 16 KB | 信任根：验证 SBL、状态记录 | 不可变 (1→0 直写) |
| **SBL** | 48 KB | 二级引导 + FASTBOOT + LCD splash | ECDSA |
| **REC** | 64 KB | 恢复模式 (SD 升级 / TDB) | ECDSA |
| **TMP** | 128 KB | 升级暂存区 (易失) | — |
| **SYSTEM** | 768 KB | 主固件：Core / driver / GUI / library | ECDSA |

### 安全启动链

```text
上电 → ELF (ECDSA 验证 SBL) → SBL (ECDSA 验证 SYSTEM/REC) → SYSTEM
                                └── OEM Unlock 时跳过验签
```

| 场景 | 耗时 |
|------|------|
| 冷启动（上电） | ~2s |
| 软复位（RESTART 标志） | ~0.5s |
| 定向重启（boot_target） | ~0.5s |

### PC 工具

三套工具在 Windows 与 Linux 上功能一致，均以 PyInstaller 打包为独立可执行文件：

| 工具 | 版本 | 协议 | 用途 |
|------|------|------|------|
| **tvidtool** | v0.1.0 | —（离线） | 视频转 `.tvid` 流，供 SD 卡播放 |
| **sbltool** | v1.0.2 | FASTBOOT CDC (PID 0x5751) | 固件烧录、分区、OEM 解锁 |
| **tdb** | v1.0.1 | Debug Bridge (PID 0x5756) | 设备 Shell、文件推送/拉取 |

---

## 硬件平台

F407CP 从板基于 STM32F407ZGT6，主要外设：

| 类别 | 器件 | 说明 |
|------|------|------|
| 显示 | 240×240 LCD | 主界面 (SPI) |
| 显示 | SSD1315 OLED | 副屏 · RTC 时钟 |
| 按键 | PA0 / PE4 / PE3 / PE2 | 上 / 下 / 确认 / 返回 |
| 存储 | SDIO + FatFs | SD 卡持久化 |
| 时钟 | RTC | 掉电走时 (备份寄存器) |
| 传感器 | BMP180 | 气压 / 温度 |
| 传感器 | JY901S | 九轴 IMU |
| 传感器 | TCS3472 | 颜色 |
| 其他 | Buzzer / Pot / LED | 蜂鸣器 / 电位器 / 指示灯 |
| 通信 | USB CDC / USART1 | 桥接 / 调试 |

> 详细硬件适配见 [slave-board/src/gui/README.md](slave-board/src/gui/README.md)。

---

## 快速开始

### 全量构建固件

```bash
cd slave-board

# 配置（首次，自动生成 ECDSA 签名密钥）
cmake --preset Release

# 构建 + 签名 + 导出 BIN 镜像
cmake --build build/Release --target factory_images

# 烧录（ELF + SBL + REC + SYSTEM）
scripts/flash.bat factory     # Windows
scripts/flash.sh factory      # Linux / macOS
```

### 构建 PC 工具（Windows）

```bash
cd win-pc

# 创建环境（首次）
conda env create -f environment.yml

# 构建（自动激活 f407cp 环境）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1
```

### 构建 PC 工具（Linux）

```bash
cd linux-pc

# 创建环境（首次）
conda env create -f environment.yml

# 构建（自动激活 f407cp 环境）
./scripts/build.sh            # 产物: dist/platform-tools/{tvidtool,sbltool,tdb}
```

### 生成并播放视频

```bash
# 转换视频为 .tvid 流
python src/tvidtool/app.py input.mp4 -o test.tvid --fps 60 --size 240x240

# 拷贝到 SD 卡（0:/storage/test.tvid），从板启动后自动播放
```

---

## 文档

| 文档 | 来源 | 说明 |
|------|------|------|
| [README.md](slave-board/README.md) | slave-board | 固件概述、分区布局、启动链、调试 |
| [README.md](win-pc/README.md) | win-pc | Windows 工具概述、构建、用法 |
| [README.md](linux-pc/README.md) | linux-pc | Linux 工具概述、构建、用法 |
| [technical-docs.md](slave-board/docs/technical-docs.md) | slave-board | 技术路线、启动流程、约束、移植 |
| [partition-docs.md](slave-board/docs/partition-docs.md) | slave-board | FASTMAP 分区布局、写权限 |
| [secure-docs.md](slave-board/docs/secure-docs.md) | slave-board | 安全策略、ECDSA 签名、OEM Lock |
| [syslog-docs.md](slave-board/docs/syslog-docs.md) | slave-board | 日志系统：等级、格式、SD 卡存储 |
| [style-docs.md](slave-board/docs/style-docs.md) | slave-board | C/C++ 代码风格规范 |
| [update-docs.md](slave-board/docs/update-docs.md) | slave-board | 固件更新记录 |

---

## 项目结构

```text
f407cp/
├── README.md                  # ← 顶层 README（本文件）
├── slave-board/               # STM32F407 固件 (C/C++, CMake)
│   ├── partitions/            # 分区固件：ELF / SBL / REC
│   ├── src/                   # SYSTEM 主应用（core/library/hardware/gui）
│   ├── scripts/               # 烧录、签名、导出脚本
│   └── docs/                  # 6 篇文档
├── win-pc/                    # Windows PC 工具 (Python, PyInstaller)
│   ├── src/                   # 源码：tvidtool / sbltool / tdb
│   └── scripts/               # 构建、清理脚本
└── linux-pc/                  # Linux PC 工具 (Python, PyInstaller)
    ├── src/                   # 源码：tvidtool / sbltool / tdb
    └── scripts/               # 构建、清理脚本
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

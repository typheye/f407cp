# JAPKit 技术说明

## 1. 概述

JAPKit 是基于 PyQt5 的 Linux 桌面调试工具，运行在 Linux 开发机上，通过 HTTP 与树莓派上的 JanPNP 服务通信。

## 2. 功能

| 标签页 | 用途 |
|--------|------|
| Gray Detection | 摄像头图像分析、HSV/LAB 灰度检测 |
| Telemetry | 电机实时位置/速度图表、3D 运动轨迹 |
| Performance | 校准测试、FPS/Ping/CPU/Mem 监控 |

## 3. 架构

### 主窗口

`JAPKitWindow(QMainWindow)` 包含一个 `QTabWidget`，使用动态标签系统：
- File → Open 子菜单打开/切换标签页
- Home 标签不可关闭
- 关闭标签自动停用对应的定时器

### 主题系统

支持三种主题模式：
- `system`：跟随桌面色彩方案（读取 GNOME `org.gnome.desktop.interface color-scheme`）
- `light`：亮色
- `dark`：暗色

通过 `apply_theme()` 函数切换。

### 平台适配（Linux）

移植过程中处理的三个平台差异：

1. **cv2 的 Qt 插件冲突** —— 依赖使用 `opencv-python-headless`。普通的
   `opencv-python` 自带 Qt 插件并在 import 时改写 `QT_QPA_PLATFORM_PLUGIN_PATH`
   （`cv2/config-3.py`），导致 PyQt5 的 `xcb` 平台插件加载失败。
2. **PyOpenGL 后端对齐** —— `app.py` 顶部根据 `QT_QPA_PLATFORM` / `DISPLAY`
   把 `PYOPENGL_PLATFORM` 设为 `egl` 或 `glx`，与 Qt 实际使用的后端保持一致；
   否则 `GetCurrentContext()` 返回 `None`，3D 视图渲染成纯色。
3. **窗口置顶** —— X11/GNOME 不会像 Windows 一样自动激活新窗口，所有
   `showMaximized()` 之后都显式调用 `raise_()` + `activateWindow()`。

### IP 对话框

启动时弹出 `IPDialog`，输入树莓派 IP、用户名和密码进行连接验证。凭据通过 `QSettings` 持久化。

### 通信

通过 HTTP 轮询树莓派 API 获取数据：
- `/api/telemetry`：电机实时数据
- `/frame/cam1`, `/frame/cam2`：摄像头帧
- `/api/system`：系统性能指标

## 4. 特殊实现

### TabBar 白线修复

Fusion 主题下启用 `setDocumentMode(True)`（拖拽排序必需）后，tab bar 下方出现 1px 浅色横线。通过安装局部 `QProxyStyle` 拦截 `PE_FrameTabWidget` / `PE_FrameTabBarBase` 绘制解决。

### 3D 视图

Telemetry 标签使用 `pyqtgraph.opengl.GLViewWidget` 绘制实时 3D 运动轨迹，支持视角旋转/缩放/平移。

## 5. 构建

```bash
scripts/setup-conda.sh    # 一键环境 + 构建
bash scripts/build.sh     # 仅构建（需 conda activate janpnp）
bash scripts/clean.sh     # 清理构建产物
```

产物：`dist/JAPKit`

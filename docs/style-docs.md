# JAPKit 代码风格

本规范适用于 JAPKit 工具代码。参照 TOS win-pc 规范。

## 基本格式

- Python 3.11+
- 使用 4 个空格缩进，不使用 Tab
- 使用双引号（与 Black 默认一致）
- 行长度上限 88 字符（Black 默认）

## 命名

| 类型 | 规则 | 示例 |
|------|------|------|
| 文件 | `snake_case` | `telemetry_window.py` |
| 类 | `PascalCase` | `JAPKitWindow`, `IPDialog` |
| 方法/函数 | `snake_case` | `apply_theme()`, `_do_connect()` |
| 变量 | `snake_case` | `pi_url`, `theme_mode` |
| 常量 | `UPPER_SNAKE_CASE` | `THEME_SYSTEM`, `THEME_DARK` |
| 私有方法/属性 | 前导 `_` | `_close_tab`, `_current_dark` |

## 文件头

每个 `.py` 文件使用标准 JanPNP 文件头：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
******************************************************************************
* @file    filename.py
* @author  JanPNP Development Team
* @brief   One-line summary.
******************************************************************************
* @attention
*
* Copyright (c) 2026 JanPNP Development Team. All rights reserved.
******************************************************************************
*/
```

## 导入顺序

1. 标准库（`sys`, `os`, `json`, `threading` 等）
2. 第三方库（`PyQt5`, `numpy`, `cv2`, `pyqtgraph`）
3. 本地模块（`depends.*`）

## Qt 特殊规范

- 使用 `PyQt5`，非 PySide
- 线程间通信使用 Qt Signal/Slot
- 暗色/亮色主题使用模块级常量管理
- TabBar 白线修复通过 `QProxyStyle` 实现

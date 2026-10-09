# JAPKit 变更记录

## 1.0.0 (2026-07-22)

- 从 `host-board/japkit/` 迁移至独立 `win-pc` 项目
- 复用 TOS win-pc 框架（PyInstaller 构建、Conda 环境管理）
- 项目结构标准化：`src/japkit/` + `scripts/` + `docs/`

### 已有功能

- IP 对话框连接验证
- Gray Detection / Telemetry / Performance 三标签页
- 暗色/亮色主题切换
- 3D 运动轨迹可视化
- TabBar 拖拽排序（白线修复）
- Telemetry 实时电机数据图表

## 2026-07-31: 3D scene expansion

- The 3D workspace continued to evolve into a full pick-and-place scene instead of a simple telemetry preview.
- PCB top preview and 3D model state loading were connected to host-board telemetry.
- The board is rendered as a solid body with thickness; the preview is drawn on the top face only.
- Placement status markers were added as vertical lines through the board:
  - pending: light blue
  - placed: green
  - abnormal: red
- Machine-side simplified models were iterated in the scene:
  - board body
  - top camera / bottom camera
  - nozzles
  - rails / frame
  - feeder zone

## 2026-08-01: Home / Parameter architecture update

- `Home` now hosts the full-screen 3D scene as the main live workspace.
- Former `Telemetry` page was renamed to `Parameter`.
- Direct tab UI entry modules were unified under `src/japkit/ui/`:
  - `gray_detection_page.py`
  - `home_page.py`
  - `parameter_page.py`
  - `performance_page.py`
- `app.py` now imports UI-layer pages instead of directly wiring Gray / Performance pages from `depends`.

## 2026-08-01: Parameter page real implementation

- `Parameter` was rebuilt into a real 7:3 horizontal layout.
- Left side is now a 2x2 live chart grid using the same pyqtgraph-style graph language as `Performance`:
  - `Position`: `X / Y / Z / H`
  - `Speed`: `XL / XR / Y / Z`
  - `Bus Voltage`: `XL / XR / Y / Z`
  - `Phase Current`: `XL / XR / Y / Z`
- Right side is now a hardware status table:
  - `Light 1 brightness`
  - `Light 2 brightness`
  - `Cooling fan`
  - `Valve 1`
  - `Valve 2`
  - `Pump 1`
  - `Pump 2`
  - `Feeder 1-12` mapped to `Idle / Running / Error`
- `Parameter` now prefers the new host-board telemetry `speed` object for `XL/XR/Y/Z` instead of reusing Cartesian `velocity`.

## 2026-08-01: Depends cleanup

- `depends/telemetry_window.py` had clearly retired outer entry code reduced:
  - removed `StatusLED`
  - removed `open_telemetry()`
- `Fetcher` and `GLW3D` were intentionally kept because `Home` and `Parameter` still depend on them.
- Legacy `TelemetryWindow` class is no longer part of the active tab flow, but was intentionally left in place for a later dedicated extraction pass to avoid destabilizing the current 3D backend.

## 2026-08-01: Physical SMD package models in Home 3D

- Added `src/japkit/depends/component_models.py` as the package geometry module.
- Defined millimetre-scale, solid multi-part models for 15 warehouse packages. Chip parts include terminals, MELF parts use horizontal cylindrical bodies, SOT/SOIC/TSSOP parts include individual leads, and LED packages include a distinct lens layer.
- X/Y dimensions are converted with Host-provided JPmm-per-mm calibration; Z dimensions remain physical millimetres in the scene.
- Occupied and hardware-detected feeder slots now render one package model at the Host-provided runtime calibrated pick center, resting on the recessed feeder slot floor.
- Successful PCB placements now replace the green status-only representation with a package model at the transformed PCB coordinate and PnP rotation. Pending and failed placements retain their blue/red vertical status lines.
- Both pyqtgraph OpenGL and QGL fallback render paths support the new component models.
- All component mesh faces are normalized outward to keep shaded colors consistent.

### Feeder tape and material appearance refinement

- Feeder component models are rotated 90 degrees into the transverse tape orientation.
- Occupied, hardware-detected feeder slots now contain a solid 2 JPmm carrier-tape layer; non-LED tape is off-white and LED tape is light charcoal.
- The carrier tape follows the physical feeder slot center while its component follows the Host-provided calibrated pick center.
- Component bodies default to black. Inventory values ending in `F` after case/space normalization are treated as capacitors and rendered yellow; terminals remain metallic silver.
- Component rotation is now applied in physical millimetres before anisotropic X/Y JPmm conversion, preventing calibration-scale distortion.

### LED appearance and nozzle collision limits

- LED packages now use a pale ceramic body and a separate near-white lens layer, keeping them visible against the dark LED carrier tape.
- Nozzle cone tips now have dynamic lower travel limits in feeder and active PCB areas.
- At a calibrated feeder pick point, the limit is the carrier-tape top plus the selected package height; elsewhere over that loaded tape, the tape top is used.
- Over the active PCB footprint, the limit is the rendered PCB top surface.
- A `0.03 JPmm` visual clearance prevents coplanar flicker, and the movable nozzle/connector assembly stops together while the guide rails remain fixed.

### Nozzle-limit partial-update crash fix

- Fixed NumPy feeder-origin arrays being evaluated as booleans in nozzle contact detection (`ValueError: truth value of an array is ambiguous`).
- Collision-limit calculations now complete before any articulated GL item is translated. An invalid contact input can no longer move only part of the machine and then repeat that partial delta on subsequent frames.
- The same explicit origin validation is used by both pyqtgraph and QGL rendering paths.

### PCB detail, persistent trails, compact ring light and feeder lighting

- Win-PC no longer downsamples the Host's 2800-6000px PCB preview to 1024px; the retained texture limit is now 4096px.
- PCB surfaces now render only the high-resolution preview texture. Gerber vector layers are no longer drawn as an overlay or fallback; `pcb_model.json` remains available for component coordinates and placement state.
- Ring-light glow keeps additive blending but now enables depth testing, so the camera housing correctly occludes the outward light layer instead of letting it show through the model.
- Home trajectory samples now carry real timestamps. Finite durations are filtered by elapsed time, and `Persistent` no longer passes through the former 6000-point/approximately-300-second cap.
- Stationary duplicate trajectory samples are omitted without deleting any actual movement points.
- Ring-light glow is now one compact layer adjacent to each lamp; telemetry levels 1-100 adjust alpha instead of creating a widening multi-ring cone.
- Feeder bodies, carrier tape, and feeder components use a dedicated higher-ambient shader. The QGL fallback applies an equivalent local color-lighting boost.
- The single ring-light glow is a thin emissive surface (`0.18 JPmm`) placed completely outside the lamp body. The top lamp mesh is mirrored below its emitting face, preventing the downward glow from appearing through the model when viewed from above.

## Verification

- Sandbox Python `py_compile` passed for:
  - `src/japkit/app.py`
  - `src/japkit/ui/home_page.py`
  - `src/japkit/ui/parameter_page.py`
  - `src/japkit/ui/gray_detection_page.py`
  - `src/japkit/ui/performance_page.py`
  - `src/japkit/depends/main_window.py`
  - `src/japkit/depends/telemetry_window.py`

## 2026-08-02: Measured PCB placement pose in Home 3D

- Home consumes per-designator `placement_inspections` from Host telemetry.
- Home also consumes bottom-camera `pick_inspections` for completed components.
  A half-height yellow line and purple compact `dX, dY dR` label preserve the
  pre-placement pick pose separately from the full-height placement result.
- The yellow line marks the physical nozzle contact point on the copied,
  post-BOM component. It uses `nozzle center - component center`, the negative
  of the held-part offset; the purple `dX/dY` values describe that same visible
  displacement. Feeder-frame values are not drawn directly in PCB world axes.
- Retained pick records created before bottom mapping version 2 are rotated 90
  degrees clockwise for review. They remain display-only and are excluded from
  Host compensation suggestions.
- A completed component model is translated and rotated by the measured
  post-placement deviation; its vertical status line remains at the original
  design coordinate.
- Pink text at the fixed line tip displays measured `dX`, `dY` in JP units and
  `dR` in degrees.
- The pyqtgraph and QGL fallback renderers implement the same behavior.
- Completed/failed PCB state remains visible after the workflow finishes for
  review.
- Home adds `Edit -> Action -> Clean PCB Modules`; it uses the same confirmation
  style as application exit and clears both Host state and the local 3D cache.
- Home adds an `Edit -> Display` checklist for `Pick and Top Camera`, `Bottom
  Camera`, `Feeders`, and `Workdesk`. All groups default to visible and retain
  their setting. PCB content, placement status lines, coordinate axes, and the
  white origin remain visible independently.
- PCB placement inspection labels use compact `dX, dY dR` numeric text without
  repeated field names or units. Their font follows camera distance and labels
  are progressively thinned/hidden when zoomed out, matching map-style label
  decluttering instead of retaining a fixed pixel footprint.

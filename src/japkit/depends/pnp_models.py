"""PNP machine model parameters and geometry helpers for JAPKit 3D views."""

import ast
import math
from pathlib import Path

import numpy as np

BOARD_EXPAND_RATIO = 0.0
BOARD_GRID_COLOR = (0.28, 0.29, 0.29, 1.0)
BOARD_GRID_WIDTH = 2
BOARD_GRID_STRIP_WIDTH = 0.45
BOARD_GRID_STRIP_HEIGHT = 0.04
BOARD_TOP_Z = 8.0
BOARD_GRID_Z = 8.03
LENS_RADIUS = 15.0
LENS_HEIGHT = 25.0
LENS_TOP_RADIUS = 10.0
LENS_TOP_HEIGHT = 15.0
LENS_BLOCK_SIZE = 40.0
LENS_BLOCK_HEIGHT = 20.0
RING_LIGHT_INNER_RADIUS = 15.5
RING_LIGHT_OUTER_RADIUS = 30.0
RING_LIGHT_HEIGHT = 15.0
RING_LIGHT_GLOW_INNER_RADIUS = 18.5
RING_LIGHT_GLOW_OUTER_RADIUS = 27.0
RING_LIGHT_GLOW_LAYERS = 4
RING_LIGHT_GLOW_STEP = 2.0
RING_LIGHT_GLOW_HEIGHT = 0.18
RING_LIGHT_GLOW_RADIUS_STEP = 1.8
RING_LIGHT_GLOW_COLOR = (1.0, 0.97, 0.78, 0.18)
RING_LIGHT_GLOW_MIN_ALPHA = 0.05
RING_LIGHT_GLOW_MAX_ALPHA = 0.40
NOZZLE_RADIUS = 8.0
NOZZLE_HEIGHT = 10.0
DEFAULT_BALANCE_Z = 20.0
LENS_COLOR = (0.06, 0.07, 0.07, 1.0)
BOARD_DARK_COLOR = (0.06, 0.07, 0.07, 1.0)
RING_LIGHT_COLOR = LENS_COLOR
NOZZLE_COLOR = (0.02, 0.28, 0.12, 1.0)
ORIGIN_BALL_COLOR = (1.0, 0.88, 0.02, 1.0)
ORIGIN_BALL_RADIUS = 4.5
CAMERA_MARKER_COLOR = (0.15, 0.15, 0.15, 1.0)
CAMERA_MARKER_RADIUS = 13.0
CAMERA_MARKER_HEIGHT = 0.12
BRASS_COLOR = (0.78, 0.55, 0.18, 1.0)
METAL_SILVER_COLOR = (0.72, 0.74, 0.76, 1.0)
DEEP_SILVER_COLOR = (0.34, 0.36, 0.38, 1.0)
DARK_BLOCK_COLOR = (0.06, 0.07, 0.07, 1.0)
LIGHT_CAP_COLOR = (0.78, 0.78, 0.74, 1.0)
NOZZLE_BOTTOM1_LINK_RADIUS = 3.0
NOZZLE_BOTTOM1_LINK_HEIGHT = 4.0
NOZZLE_BOTTOM2_LINK_RADIUS = 6.0
NOZZLE_BOTTOM2_LINK_HEIGHT = 11.0
NOZZLE_BOTTOM_LINK_HEIGHT = NOZZLE_BOTTOM1_LINK_HEIGHT + NOZZLE_BOTTOM2_LINK_HEIGHT
NOZZLE_BLOCK_SIZE = 20.0
NOZZLE_BLOCK_HEIGHT = 30.0
NOZZLE_TOP_LINK_RADIUS = 4.0
NOZZLE_TOP_LINK_HEIGHT = 10.0
NOZZLE_CAP_RADIUS = 6.0
NOZZLE_CAP_HEIGHT = 5.0
HEAD_CONNECTOR_Y = 15.0
HEAD_CONNECTOR_Z = 20.0
HEAD_CONNECTOR_X = 5.0
GUIDE_RAIL_Y = 10.0
GUIDE_RAIL_Z = 80.0
GUIDE_RAIL_X = 5.0
RAIL_FRAME_X = 5.0
RAIL_FRAME_Z = 80.0
CAMERA_LINK_Y = 20.0
CAMERA_LINK_Z = 15.0
FEEDER_BODY_X = 45.0
FEEDER_BODY_Y = 11.0
FEEDER_BODY_Z_BOTTOM = -40 + BOARD_TOP_Z
FEEDER_BODY_Z_HEIGHT = BOARD_TOP_Z - FEEDER_BODY_Z_BOTTOM
FEEDER_SLOT_X = 15.0
FEEDER_SLOT_Y = 5.0
FEEDER_SLOT_DEPTH = 4.0
FEEDER_SLOT_WALL = 0.35
FEEDER_SLOT_FLOOR = 0.08
FEEDER_SLOT_RECESS = 0.45
FEEDER_BODY_COLOR = (0.08, 0.09, 0.09, 1.0)
FEEDER_SLOT_COLOR = (0.015, 0.017, 0.018, 1.0)
FEEDER_SHADER = "feederAmbient"
FEEDER_FAIL_STATE = 2
FEEDER_BACK1_X = 15.0
FEEDER_BACK1_Y = 11.0
FEEDER_BACK1_Z = 20.0
FEEDER_BACK2_X = 40.0
FEEDER_BACK2_Y = 11.0
FEEDER_BACK2_Z = 50.0
FEEDER_TOP_TRAP_BOTTOM_X = 18.0
FEEDER_TOP_TRAP_TOP_X = 12.0
FEEDER_TOP_TRAP_Y = 11.0
FEEDER_TOP_TRAP_Z = 9.0
PCB_MODEL_BODY_COLOR = (0.02, 0.28, 0.14, 1.0)
PCB_MODEL_SILK_COLOR = (0.92, 0.92, 0.86, 1.0)
PCB_MODEL_COPPER_COLOR = (0.08, 0.55, 0.30, 1.0)
PCB_MODEL_PASTE_COLOR = (0.62, 0.62, 0.62, 1.0)
PCB_MODEL_TOP_Z = BOARD_TOP_Z + 0.5
PCB_MODEL_LINE_PENDING_COLOR = (0.55, 0.90, 1.0, 1.0)
PCB_MODEL_LINE_DONE_COLOR = (0.05, 0.95, 0.20, 1.0)
PCB_MODEL_LINE_FAILED_COLOR = (1.0, 0.05, 0.04, 1.0)
PCB_MODEL_INSPECTION_TEXT_COLOR = (1.0, 0.20, 0.68, 1.0)
PCB_MODEL_PICK_INSPECTION_LINE_COLOR = (1.0, 0.82, 0.05, 1.0)
PCB_MODEL_PICK_INSPECTION_TEXT_COLOR = (0.72, 0.28, 1.0, 1.0)
PCB_MODEL_STATUS_LINE_HEIGHT = 7.0
FALLBACK_FEEDERS_ORIGIN = {
    "FED1": (82.0, 202.0),
    "FED2": (82.0, 190.0),
    "FED3": (82.0, 178.0),
    "FED4": (82.0, 166.0),
    "FED5": (82.0, 154.0),
    "FED6": (82.0, 142.0),
    "FED7": (82.0, 130.0),
    "FED8": (82.0, 118.0),
    "FED9": (82.0, 106.0),
    "FED10": (82.0, 94.0),
    "FED11": (82.0, 82.0),
    "FED12": (82.0, 70.0),
}


def _load_feeders_origin_from_coord_utils():
    """Load default feeder coordinates from host-board coord_utils.py when available."""
    try:
        root = Path(__file__).resolve().parents[4]
        coord_path = root / "host-board" / "janpnp" / "server" / "core" / "component" / "coord_utils.py"
        text = coord_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(coord_path))
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "FEEDERS_ORIGIN" for t in node.targets)
            ):
                data = ast.literal_eval(node.value)
                return {
                    str(key).upper(): (float(value[0]), float(value[1]))
                    for key, value in data.items()
                    if str(key).upper().startswith("FED") and len(value) >= 2
                }
    except Exception:
        pass
    return dict(FALLBACK_FEEDERS_ORIGIN)


DEFAULT_FEEDERS_ORIGIN = _load_feeders_origin_from_coord_utils()


def _expanded_board_top_points(points, ratio=BOARD_EXPAND_RATIO):
    pts = np.array(points, dtype=float)
    center = pts[:, :2].mean(axis=0)
    expanded = pts.copy()
    expanded[:, :2] = center + (pts[:, :2] - center) * (1.0 + ratio * 2.0)
    return expanded


def _grid_lines_for_quad(quad, divisions=9, z=BOARD_GRID_Z):
    q = np.array(quad, dtype=float)
    p0, p1, p2, p3 = q[0], q[1], q[2], q[3]
    lines = []
    for i in range(divisions + 1):
        t = i / float(divisions)
        a = (1.0 - t) * p0 + t * p1
        b = (1.0 - t) * p3 + t * p2
        c = (1.0 - t) * p0 + t * p3
        d = (1.0 - t) * p1 + t * p2
        a[2] = b[2] = c[2] = d[2] = z
        lines.append((a, b))
        lines.append((c, d))
    return lines


def _line_segments_to_nan_array(segments):
    pos = np.empty((len(segments) * 3, 3), dtype=float)
    for i, (a, b) in enumerate(segments):
        pos[i * 3] = a
        pos[i * 3 + 1] = b
        pos[i * 3 + 2] = np.nan
    return pos


def _pcb_model_rotate_xy(local_x, local_y, rotate_deg):
    if not rotate_deg:
        return local_x, local_y
    rad = math.radians(float(rotate_deg))
    ca = math.cos(rad)
    sa = math.sin(rad)
    return local_x * ca - local_y * sa, local_x * sa + local_y * ca


def _pcb_model_local_xy(x, y, center, scale, rotate_deg=180.0):
    """Map Gerber/PnP mm coordinates to local JPmm board coordinates."""
    cx, cy = center
    sx, sy = scale
    component_x_mm = -(float(y) - float(cy))
    component_y_mm = float(x) - float(cx)
    # Match the machine path exactly: rotate the PCB-local millimetre vector,
    # then apply each axis' JPmm scale and the placement subtraction. Rotating
    # an already anisotropically scaled vector drifts increasingly near edges.
    rotated_x_mm, rotated_y_mm = _pcb_model_rotate_xy(
        component_x_mm, component_y_mm, float(rotate_deg) - 180.0
    )
    return -rotated_x_mm * float(sx), -rotated_y_mm * float(sy)


def _pcb_model_segment_array(model, state):
    pcb = (model or {}).get("pcb", {})
    center = pcb.get("center") or [0.0, 0.0]
    scale_data = (state or {}).get("scale_jp_per_mm") or {}
    scale = (
        abs(float(scale_data.get("x", 1.0) or 1.0)),
        abs(float(scale_data.get("y", 1.0) or 1.0)),
    )
    pose = (state or {}).get("center_jp") or {}
    rotate_deg = float((state or {}).get("rotation_deg", 180.0) or 0.0)
    ox = float(pose.get("x", 0.0) or 0.0)
    oy = float(pose.get("y", 0.0) or 0.0)
    thickness = max(0.05, float((state or {}).get("thickness", 0.5) or 0.5))
    top_z = BOARD_TOP_Z + thickness + 0.035

    result = {}
    for layer, segments in ((model or {}).get("layers") or {}).items():
        line_points = []
        for seg in segments or []:
            if len(seg) < 4:
                continue
            x1, y1 = _pcb_model_local_xy(seg[0], seg[1], center, scale, rotate_deg)
            x2, y2 = _pcb_model_local_xy(seg[2], seg[3], center, scale, rotate_deg)
            line_points.append(
                (
                    np.array([ox + x1, oy + y1, top_z], dtype=float),
                    np.array([ox + x2, oy + y2, top_z], dtype=float),
                )
            )
        if line_points:
            result[layer] = _line_segments_to_nan_array(line_points)
    return result


def _pcb_model_component_status_lines(model, state):
    pcb = (model or {}).get("pcb", {})
    center = pcb.get("center") or [0.0, 0.0]
    scale_data = (state or {}).get("scale_jp_per_mm") or {}
    scale = (
        abs(float(scale_data.get("x", 1.0) or 1.0)),
        abs(float(scale_data.get("y", 1.0) or 1.0)),
    )
    pose = (state or {}).get("center_jp") or {}
    rotate_deg = float((state or {}).get("rotation_deg", 180.0) or 0.0)
    ox = float(pose.get("x", 0.0) or 0.0)
    oy = float(pose.get("y", 0.0) or 0.0)
    thickness = max(0.05, float((state or {}).get("thickness", 0.5) or 0.5))
    visible = {
        str(item).strip().upper()
        for item in ((state or {}).get("visible_designators") or [])
        if str(item).strip()
    }
    completed = {
        str(item).strip().upper()
        for item in ((state or {}).get("completed_designators") or [])
        if str(item).strip()
    }
    failed = {
        str(item).strip().upper()
        for item in ((state or {}).get("failed_designators") or [])
        if str(item).strip()
    }
    line_bottom = BOARD_TOP_Z - 0.12
    line_top = BOARD_TOP_Z + thickness + PCB_MODEL_STATUS_LINE_HEIGHT
    lines = []
    for comp in (model or {}).get("components") or []:
        try:
            designator = str(comp.get("designator", "") or "").strip().upper()
            if visible and designator not in visible:
                continue
            lx, ly = _pcb_model_local_xy(
                comp.get("x", 0.0),
                comp.get("y", 0.0),
                center,
                scale,
                rotate_deg,
            )
            color = PCB_MODEL_LINE_PENDING_COLOR
            if designator in completed:
                color = PCB_MODEL_LINE_DONE_COLOR
            if designator in failed:
                color = PCB_MODEL_LINE_FAILED_COLOR
            x = ox + lx
            y = oy + ly
            lines.append(
                (
                    designator,
                    np.array([[x, y, line_bottom], [x, y, line_top]], dtype=float),
                    color,
                )
            )
        except Exception:
            continue
    return lines


def _pcb_model_inspection_adjustment(state, designator):
    inspection = ((state or {}).get("placement_inspections") or {}).get(
        str(designator or "").strip().upper()
    ) or {}
    if not inspection.get("found", False):
        return 0.0, 0.0, 0.0
    if inspection.get("offset_valid") is False:
        return 0.0, 0.0, 0.0
    try:
        # Host publishes these values in PCB/preview JP axes. Only a registered
        # footprint-relative measurement is allowed to move the component.
        return (
            float(inspection.get("offset_x_jp", 0.0) or 0.0),
            float(inspection.get("offset_y_jp", 0.0) or 0.0),
            float(inspection.get("rotation_offset_deg", 0.0) or 0.0),
        )
    except Exception:
        return 0.0, 0.0, 0.0


def _pcb_model_display_inspection_adjustment(state, designator):
    """Return the measured placement vector for telemetry labels.

    ``offset_valid`` gates compensation and pass/fail decisions, but it must
    not erase the camera measurement from the operator view when footprint
    matching is unavailable.  The camera vector is therefore displayed as
    evidence while the nominal model remains unchanged.
    """
    inspection = ((state or {}).get("placement_inspections") or {}).get(
        str(designator or "").strip().upper()
    ) or {}
    if not inspection.get("found", False):
        return 0.0, 0.0, 0.0
    try:
        # These fields are already transformed into the board/preview JP
        # axes by Host.  camera_offset_* is retained separately as raw camera
        # evidence and must not be drawn directly in board coordinates.
        x = inspection.get("offset_x_jp", 0.0)
        y = inspection.get("offset_y_jp", 0.0)
        return float(x or 0.0), float(y or 0.0), float(
            inspection.get("rotation_offset_deg", 0.0) or 0.0
        )
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0


def _compact_inspection_value(value):
    value = 0.0 if abs(float(value)) < 0.005 else float(value)
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _pcb_model_pick_contact_offset(inspection):
    """Return nozzle contact minus component center in post-BOM JP axes."""
    try:
        if "contact_offset_x_jp" in inspection or "contact_offset_y_jp" in inspection:
            contact = (
                float(inspection.get("contact_offset_x_jp", 0.0) or 0.0),
                float(inspection.get("contact_offset_y_jp", 0.0) or 0.0),
            )
        elif "held_offset_x_jp" in inspection or "held_offset_y_jp" in inspection:
            contact = (
                -float(inspection.get("held_offset_x_jp", 0.0) or 0.0),
                -float(inspection.get("held_offset_y_jp", 0.0) or 0.0),
            )
        else:
            dx = float(inspection.get("offset_x_jp", 0.0) or 0.0)
            dy = float(inspection.get("offset_y_jp", 0.0) or 0.0)
            if inspection.get("offset_coordinate_frame") == "feeder_pick":
                angle = math.radians(
                    float(inspection.get("expected_rotation_deg", 0.0) or 0.0)
                )
                held_x, held_y = (
                    math.cos(angle) * dx - math.sin(angle) * dy,
                    math.sin(angle) * dx + math.cos(angle) * dy,
                )
            else:
                # Legacy Host records exposed the post-BOM held vector directly.
                held_x, held_y = dx, dy
            contact = (-held_x, -held_y)

        if int(inspection.get("bottom_mapping_version", 0) or 0) < 2:
            # Records from the previous mapping are 90 degrees CCW from the
            # physically observed contact point. Rotate them clockwise for
            # retained-order review without admitting them into compensation.
            contact = (contact[1], -contact[0])
        return contact
    except Exception:
        return 0.0, 0.0


def _pcb_model_pick_inspection_lines(model, state):
    inspections = (state or {}).get("pick_inspections") or {}
    placement_inspections = (state or {}).get("placement_inspections") or {}
    lines = []
    for designator, points, _color in _pcb_model_component_status_lines(model, state):
        inspection = inspections.get(designator) or {}
        placement = placement_inspections.get(designator) or {}
        if not inspection.get("found", False) or not placement.get("found", False):
            continue
        points = np.asarray(points, dtype=float)
        dx, dy = _pcb_model_pick_contact_offset(inspection)
        inspect_x, inspect_y, _inspect_angle = _pcb_model_inspection_adjustment(
            state, designator
        )
        # The yellow marker identifies the opaque, post-placement inspection
        # model. The frozen release model is intentionally left unmarked.
        points[:, 0] += inspect_x
        points[:, 1] += inspect_y
        half_top = points[0] + (points[1] - points[0]) * 0.5
        rotation = float(inspection.get("rotation_offset_deg", 0.0) or 0.0)
        rotation = 0.0 if abs(rotation) < 0.005 else rotation
        lines.append(
            (
                designator,
                np.array([points[0], half_top], dtype=float),
                half_top + np.array([0.0, 0.0, 0.15]),
                f"{_compact_inspection_value(dx)}, "
                f"{_compact_inspection_value(dy)} {rotation:.2f}",
            )
        )
    return lines


def _pcb_model_released_component(state, designator):
    """Return the immutable board-space pose captured when vacuum was released."""
    key = str(designator or "").strip().upper()
    released = ((state or {}).get("released_components") or {}).get(key) or {}
    center = released.get("center_jp") or {}
    try:
        return {
            "x": float(center["x"]),
            "y": float(center["y"]),
            "rotation_deg": float(released.get("rotation_deg", 0.0) or 0.0),
            "pick_inspection": released.get("pick_inspection") or {},
        }
    except (KeyError, TypeError, ValueError):
        return None


def _pcb_model_held_component(model, state):
    """Resolve the model/material and measured pose of the currently held part."""
    held = (state or {}).get("held_component") or {}
    designator = str(held.get("designator", "") or "").strip().upper()
    nozzle = str(held.get("nozzle", "") or "").strip().lower()
    completed = {
        str(item).strip().upper()
        for item in ((state or {}).get("completed_designators") or [])
    }
    if not designator or nozzle not in ("pl", "pr") or designator in completed:
        return None
    component = next(
        (
            item
            for item in ((model or {}).get("components") or [])
            if str(item.get("designator", "") or "").strip().upper() == designator
        ),
        None,
    )
    if not component:
        return None
    material = ((state or {}).get("component_materials") or {}).get(designator) or {}
    inspection = held.get("inspection") or {}
    contact_x, contact_y = _pcb_model_pick_contact_offset(inspection)
    board_rotation = float((state or {}).get("rotation_deg", 180.0) or 0.0)
    angle = float(held.get("rotation_deg", 0.0) or 0.0) + 90.0 + board_rotation
    angle += float(inspection.get("rotation_offset_deg", 0.0) or 0.0)
    return {
        "designator": designator,
        "nozzle": nozzle,
        "package": material.get("package") or component.get("package"),
        "value": material.get("value") or component.get("value"),
        "contact_x": contact_x,
        "contact_y": contact_y,
        "rotation_deg": angle,
        "inspection": inspection,
        "label": (
            f"{_compact_inspection_value(contact_x)}, "
            f"{_compact_inspection_value(contact_y)} "
            f"{float(inspection.get('rotation_offset_deg', 0.0) or 0.0):.2f}"
        ),
    }


def _pcb_model_inspection_labels(model, state):
    inspections = (state or {}).get("placement_inspections") or {}
    completed = {
        str(item).strip().upper()
        for item in ((state or {}).get("completed_designators") or [])
    }
    labels = []
    for designator, points, _color in _pcb_model_component_status_lines(model, state):
        inspection = inspections.get(designator) or {}
        if (
            designator not in completed
            or not inspection.get("found", False)
            or inspection.get("offset_valid") is False
        ):
            continue
        dx, dy, rotation = _pcb_model_display_inspection_adjustment(
            state, designator
        )
        rotation = 0.0 if abs(float(rotation)) < 0.005 else float(rotation)
        label_position = np.asarray(points[1], dtype=float).copy()
        label_position[0] += dx
        label_position[1] += dy
        label_position[2] += 0.15
        labels.append(
            (
                label_position,
                f"{_compact_inspection_value(dx)}, "
                f"{_compact_inspection_value(dy)} {rotation:.2f}",
            )
        )
    return labels


def _orient_faces_outward(verts, faces):
    verts = np.array(verts, dtype=float)
    faces = np.array(faces, dtype=int).copy()
    center = verts.mean(axis=0)
    for idx, (a, b, c) in enumerate(faces):
        pa = verts[a]
        pb = verts[b]
        pc = verts[c]
        normal = np.cross(pb - pa, pc - pa)
        face_center = (pa + pb + pc) / 3.0
        if np.dot(normal, face_center - center) < 0:
            faces[idx] = [a, c, b]
    return faces


def _mesh_cylinder(radius=LENS_RADIUS, height=LENS_HEIGHT, cols=32):
    verts = []
    faces = []
    for z in (0.0, height):
        for i in range(cols):
            a = 2.0 * math.pi * i / cols
            verts.append((math.cos(a) * radius, math.sin(a) * radius, z))
    bottom_center = len(verts)
    verts.append((0.0, 0.0, 0.0))
    top_center = len(verts)
    verts.append((0.0, 0.0, height))
    for i in range(cols):
        j = (i + 1) % cols
        faces.append((i, j, cols + j))
        faces.append((i, cols + j, cols + i))
        faces.append((bottom_center, j, i))
        faces.append((top_center, cols + i, cols + j))
    verts = np.array(verts, dtype=float)
    faces = _orient_faces_outward(verts, faces)
    return verts, faces


def _mesh_ring_cylinder(inner_radius, outer_radius, height, cols=48):
    verts = []
    for z in (0.0, height):
        for radius in (outer_radius, inner_radius):
            for i in range(cols):
                a = 2.0 * math.pi * i / cols
                verts.append((math.cos(a) * radius, math.sin(a) * radius, z))
    bottom_outer = 0
    bottom_inner = cols
    top_outer = cols * 2
    top_inner = cols * 3
    faces = []
    for i in range(cols):
        j = (i + 1) % cols
        faces.append((bottom_outer + i, bottom_outer + j, top_outer + j))
        faces.append((bottom_outer + i, top_outer + j, top_outer + i))
        faces.append((bottom_inner + j, bottom_inner + i, top_inner + i))
        faces.append((bottom_inner + j, top_inner + i, top_inner + j))
        faces.append((bottom_outer + j, bottom_outer + i, bottom_inner + i))
        faces.append((bottom_outer + j, bottom_inner + i, bottom_inner + j))
        faces.append((top_outer + i, top_outer + j, top_inner + j))
        faces.append((top_outer + i, top_inner + j, top_inner + i))
    return np.array(verts, dtype=float), np.array(faces, dtype=int)


def _mesh_inverted_cone(radius=NOZZLE_RADIUS, height=NOZZLE_HEIGHT, cols=32):
    verts = []
    for i in range(cols):
        a = 2.0 * math.pi * i / cols
        verts.append((math.cos(a) * radius, math.sin(a) * radius, 0.0))
    base_center = len(verts)
    verts.append((0.0, 0.0, 0.0))
    tip = len(verts)
    verts.append((0.0, 0.0, -height))
    faces = []
    for i in range(cols):
        j = (i + 1) % cols
        faces.append((i, j, tip))
        faces.append((base_center, j, i))
    verts = np.array(verts, dtype=float)
    faces = _orient_faces_outward(verts, faces)
    return verts, faces


def _mesh_box(width=NOZZLE_BLOCK_SIZE, depth=NOZZLE_BLOCK_SIZE, height=NOZZLE_BLOCK_HEIGHT):
    hx = width / 2.0
    hy = depth / 2.0
    verts = np.array([
        [-hx, -hy, 0.0],
        [hx, -hy, 0.0],
        [hx, hy, 0.0],
        [-hx, hy, 0.0],
        [-hx, -hy, height],
        [hx, -hy, height],
        [hx, hy, height],
        [-hx, hy, height],
    ], dtype=float)
    faces = np.array([
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
    ], dtype=int)
    faces = _orient_faces_outward(verts, faces)
    return verts, faces


def _mesh_feeder_top_trapezoid(origin_x, origin_y):
    y0 = float(origin_y) - FEEDER_TOP_TRAP_Y / 2.0
    y1 = float(origin_y) + FEEDER_TOP_TRAP_Y / 2.0
    x0 = float(origin_x)
    zb = BOARD_TOP_Z
    zt = BOARD_TOP_Z + FEEDER_TOP_TRAP_Z
    bottom_x1 = x0 + FEEDER_TOP_TRAP_BOTTOM_X
    top_x0 = bottom_x1 - FEEDER_TOP_TRAP_TOP_X
    verts = np.array([
        [x0, y0, zb],
        [bottom_x1, y0, zb],
        [bottom_x1, y0, zt],
        [top_x0, y0, zt],
        [x0, y1, zb],
        [bottom_x1, y1, zb],
        [bottom_x1, y1, zt],
        [top_x0, y1, zt],
    ], dtype=float)
    faces = np.array([
        [0, 2, 1], [0, 3, 2],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [3, 7, 6], [3, 6, 2],
        [0, 4, 7], [0, 7, 3],
        [1, 2, 6], [1, 6, 5],
    ], dtype=int)
    faces = _orient_faces_outward(verts, faces)
    return verts, faces


def _mirror_mesh_z(verts, faces):
    mirrored_verts = np.array(verts, dtype=float).copy()
    mirrored_verts[:, 2] *= -1.0
    mirrored_faces = np.array(faces, dtype=int).copy()
    mirrored_faces[:, [1, 2]] = mirrored_faces[:, [2, 1]]
    return mirrored_verts, mirrored_faces


def _mesh_uv_sphere(radius=ORIGIN_BALL_RADIUS, rows=16, cols=32):
    verts = []
    for r in range(rows + 1):
        phi = math.pi * r / rows
        z = math.cos(phi) * radius
        ring_radius = math.sin(phi) * radius
        for c in range(cols):
            theta = 2.0 * math.pi * c / cols
            verts.append((math.cos(theta) * ring_radius, math.sin(theta) * ring_radius, z))
    faces = []
    for r in range(rows):
        for c in range(cols):
            a = r * cols + c
            b = r * cols + (c + 1) % cols
            d = (r + 1) * cols + c
            e = (r + 1) * cols + (c + 1) % cols
            faces.append((a, d, b))
            faces.append((b, d, e))
    verts = np.array(verts, dtype=float)
    faces = _orient_faces_outward(verts, faces)
    return verts, faces


def _origin_point(origins, key):
    data = origins.get(key, {}) if isinstance(origins, dict) else {}
    try:
        return float(data["x"]), float(data["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _tool_offsets_from_settings(settings):
    origins = settings.get("pnp", {}).get("cal", {}).get("origin", {}) if isinstance(settings, dict) else {}
    visit = _origin_point(origins, "visit_2cam")
    pl = _origin_point(origins, "pl_check")
    pr = _origin_point(origins, "pr_check")
    if not visit or not pl or not pr:
        return None
    vx, vy = visit
    return {
        "pl": (vx - pl[0], vy - pl[1]),
        "pr": (vx - pr[0], vy - pr[1]),
    }


def _tool_offsets_from_pcb_state(state):
    """Read the authoritative runtime calibration used by the active order."""
    raw = (state or {}).get("tool_offsets_jp") or {}
    result = {}
    for key in ("pl", "pr"):
        value = raw.get(key) or {}
        try:
            result[key] = (float(value["x"]), float(value["y"]))
        except (KeyError, TypeError, ValueError):
            return None
    return result


def _balance_z_from_settings(settings):
    try:
        value = settings.get("pnp", {}).get("pick", {}).get("balance", DEFAULT_BALANCE_Z)
        return float(value)
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_BALANCE_Z


def _visit_2cam_from_settings(settings):
    origins = settings.get("pnp", {}).get("cal", {}).get("origin", {}) if isinstance(settings, dict) else {}
    return _origin_point(origins, "visit_2cam")


def _feeder_sort_key(key):
    try:
        return int(str(key).upper().replace("FED", ""))
    except ValueError:
        return 999


def _feeder_model_boxes(x, y):
    z0 = BOARD_TOP_Z - FEEDER_SLOT_DEPTH - FEEDER_SLOT_RECESS
    wall_height = FEEDER_SLOT_DEPTH + FEEDER_SLOT_RECESS
    under_slot_height = max(0.0, z0 - FEEDER_BODY_Z_BOTTOM)
    side_x = (FEEDER_BODY_X - FEEDER_SLOT_X) / 2.0
    side_y = (FEEDER_BODY_Y - FEEDER_SLOT_Y) / 2.0
    body_back_face_x = x - FEEDER_BODY_X / 2.0
    back1_center_x = body_back_face_x - FEEDER_BACK1_X / 2.0
    back1_back_face_x = body_back_face_x - FEEDER_BACK1_X
    back2_center_x = back1_back_face_x - FEEDER_BACK2_X / 2.0
    boxes = [
        (FEEDER_BODY_COLOR, x - FEEDER_SLOT_X / 2.0 - side_x / 2.0, y, FEEDER_BODY_Z_BOTTOM, side_x, FEEDER_BODY_Y, FEEDER_BODY_Z_HEIGHT),
        (FEEDER_BODY_COLOR, x + FEEDER_SLOT_X / 2.0 + side_x / 2.0, y, FEEDER_BODY_Z_BOTTOM, side_x, FEEDER_BODY_Y, FEEDER_BODY_Z_HEIGHT),
        (FEEDER_BODY_COLOR, x, y - FEEDER_SLOT_Y / 2.0 - side_y / 2.0, FEEDER_BODY_Z_BOTTOM, FEEDER_SLOT_X, side_y, FEEDER_BODY_Z_HEIGHT),
        (FEEDER_BODY_COLOR, x, y + FEEDER_SLOT_Y / 2.0 + side_y / 2.0, FEEDER_BODY_Z_BOTTOM, FEEDER_SLOT_X, side_y, FEEDER_BODY_Z_HEIGHT),
        (FEEDER_BODY_COLOR, x, y, FEEDER_BODY_Z_BOTTOM, FEEDER_SLOT_X, FEEDER_SLOT_Y, under_slot_height),
        (FEEDER_BODY_COLOR, back1_center_x, y, BOARD_TOP_Z - FEEDER_BACK1_Z, FEEDER_BACK1_X, FEEDER_BACK1_Y, FEEDER_BACK1_Z),
        (FEEDER_BODY_COLOR, back2_center_x, y, BOARD_TOP_Z - FEEDER_BACK2_Z, FEEDER_BACK2_X, FEEDER_BACK2_Y, FEEDER_BACK2_Z),
        (FEEDER_SLOT_COLOR, x, y, z0, FEEDER_SLOT_X, FEEDER_SLOT_Y, FEEDER_SLOT_FLOOR),
        (FEEDER_SLOT_COLOR, x, y - FEEDER_SLOT_Y / 2.0 + FEEDER_SLOT_WALL / 2.0, z0, FEEDER_SLOT_X, FEEDER_SLOT_WALL, wall_height),
        (FEEDER_SLOT_COLOR, x, y + FEEDER_SLOT_Y / 2.0 - FEEDER_SLOT_WALL / 2.0, z0, FEEDER_SLOT_X, FEEDER_SLOT_WALL, wall_height),
        (FEEDER_SLOT_COLOR, x - FEEDER_SLOT_X / 2.0 + FEEDER_SLOT_WALL / 2.0, y, z0, FEEDER_SLOT_WALL, FEEDER_SLOT_Y, wall_height),
        (FEEDER_SLOT_COLOR, x + FEEDER_SLOT_X / 2.0 - FEEDER_SLOT_WALL / 2.0, y, z0, FEEDER_SLOT_WALL, FEEDER_SLOT_Y, wall_height),
    ]
    return [box for box in boxes if box[4] > 0 and box[5] > 0 and box[6] > 0]


def _feeder_top_trapezoid_mesh(x, y):
    body_back_face_x = float(x) - FEEDER_BODY_X / 2.0
    back1_back_face_x = body_back_face_x - FEEDER_BACK1_X
    back2_back_face_x = back1_back_face_x - FEEDER_BACK2_X
    return _mesh_feeder_top_trapezoid(back2_back_face_x, y)


def _normalize_feeder_states(value):
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = value
    else:
        return []
    states = []
    for part in parts:
        try:
            states.append(int(part))
        except (TypeError, ValueError):
            states.append(FEEDER_FAIL_STATE)
    return states


def _active_feeder_keys_from_telemetry(data):
    if not isinstance(data, dict):
        return set()
    states = _normalize_feeder_states(data.get("feeders", data.get("FED", data.get("fed"))))
    if not states:
        return set(DEFAULT_FEEDERS_ORIGIN.keys())
    return {f"FED{idx + 1}" for idx, state in enumerate(states[:12]) if state != FEEDER_FAIL_STATE}


def _nozzle_visual_z_offsets(tool_offsets, current_z, balance_z):
    if not tool_offsets:
        return {}
    left_key = min(tool_offsets, key=lambda k: tool_offsets[k][1])
    dz = float(current_z or 0.0) - float(balance_z)
    result = {}
    for key in tool_offsets:
        result[key] = -dz if key == left_key else dz
    return result


def _head_connector_local_poses(tool_offsets):
    if not tool_offsets or "pl" not in tool_offsets or "pr" not in tool_offsets:
        return None
    pl_x, pl_y = tool_offsets["pl"]
    pr_x, pr_y = tool_offsets["pr"]
    center_x = (float(pl_x) + float(pr_x)) / 2.0
    center_y = (float(pl_y) + float(pr_y)) / 2.0
    block_bottom_z = NOZZLE_HEIGHT + NOZZLE_BOTTOM_LINK_HEIGHT
    connector_bottom_z = block_bottom_z + (NOZZLE_BLOCK_HEIGHT - HEAD_CONNECTOR_Z) / 2.0
    block_back_x = center_x - NOZZLE_BLOCK_SIZE / 2.0
    connector_center_x = block_back_x - HEAD_CONNECTOR_X / 2.0
    rail_center_x = connector_center_x - HEAD_CONNECTOR_X / 2.0 - GUIDE_RAIL_X / 2.0
    frame_y = abs(float(pl_y) - float(pr_y)) + GUIDE_RAIL_Y * 1.0
    frame_center_x = rail_center_x - GUIDE_RAIL_X / 2.0 - RAIL_FRAME_X / 2.0
    frame_pos_x_face = frame_center_x + RAIL_FRAME_X / 2.0
    camera_block_front_x_face = LENS_BLOCK_SIZE / 2.0
    camera_link_min_x = min(frame_pos_x_face, camera_block_front_x_face)
    camera_link_max_x = max(frame_pos_x_face, camera_block_front_x_face)
    camera_link_x = max(1.0, camera_link_max_x - camera_link_min_x)
    camera_link_center_x = (camera_link_min_x + camera_link_max_x) / 2.0
    camera_link_bottom_z = LENS_HEIGHT + LENS_TOP_HEIGHT + LENS_BLOCK_HEIGHT / 2.0 - CAMERA_LINK_Z / 2.0
    return {
        "connectors": [
            (connector_center_x, float(pl_y), connector_bottom_z),
            (connector_center_x, float(pr_y), connector_bottom_z),
        ],
        "rails": [
            (rail_center_x, float(pl_y), 0.0),
            (rail_center_x, float(pr_y), 0.0),
        ],
        "frame": (frame_center_x, center_y, 0.0, RAIL_FRAME_X, frame_y, RAIL_FRAME_Z),
        "camera_link": (
            camera_link_center_x,
            0.0,
            camera_link_bottom_z,
            camera_link_x,
            CAMERA_LINK_Y,
            CAMERA_LINK_Z,
        ),
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("_") or name.isupper()
]

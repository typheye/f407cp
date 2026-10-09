"""Industry-sized SMD package meshes for the JAPKit machine preview.

Package dimensions are stored in physical millimetres.  Horizontal geometry
is converted to the machine's JPmm axes only when a model is instantiated;
vertical dimensions remain physical millimetres in the 3D scene.
"""

from dataclasses import dataclass
import math

import numpy as np


COMPONENT_BODY_COLOR = (0.045, 0.050, 0.055, 1.0)
COMPONENT_TERMINAL_COLOR = (0.72, 0.76, 0.80, 1.0)
COMPONENT_LED_COLOR = (0.78, 0.80, 0.77, 1.0)
COMPONENT_LED_LENS_COLOR = (0.90, 0.96, 0.92, 1.0)
COMPONENT_CAPACITOR_COLOR = (0.90, 0.72, 0.12, 1.0)
FEEDER_TAPE_COLOR = (0.82, 0.80, 0.71, 1.0)
FEEDER_LED_TAPE_COLOR = (0.16, 0.17, 0.18, 1.0)
FEEDER_TAPE_HEIGHT = 2.0


@dataclass(frozen=True)
class PackageDefinition:
    package: str
    family: str
    length: float
    width: float
    height: float
    body_length: float = 0.0
    body_width: float = 0.0
    pins: int = 0
    pitch: float = 0.0


PACKAGE_DEFINITIONS = {
    "SMD01005": PackageDefinition("SMD01005", "chip", 0.40, 0.20, 0.13),
    "SMD0201": PackageDefinition("SMD0201", "chip", 0.60, 0.30, 0.23),
    "SMD0402": PackageDefinition("SMD0402", "chip", 1.00, 0.50, 0.35),
    "SMD0603": PackageDefinition("SMD0603", "chip", 1.60, 0.80, 0.55),
    "SMD0805": PackageDefinition("SMD0805", "chip", 2.00, 1.25, 0.65),
    "SMD1206": PackageDefinition("SMD1206", "chip", 3.20, 1.60, 0.70),
    "LED-0603": PackageDefinition("LED-0603", "led", 1.60, 0.80, 0.60),
    "LED-0805": PackageDefinition("LED-0805", "led", 2.00, 1.25, 0.75),
    "LED-1206": PackageDefinition("LED-1206", "led", 3.20, 1.60, 0.85),
    "MELF-2012": PackageDefinition("MELF-2012", "melf", 2.00, 1.20, 1.20),
    "MELF-3514": PackageDefinition("MELF-3514", "melf", 3.50, 1.40, 1.40),
    "SOT-23": PackageDefinition(
        "SOT-23", "sot", 2.90, 2.80, 1.10, 2.90, 1.30, 3, 0.95
    ),
    "SOT-143": PackageDefinition(
        "SOT-143", "sot", 2.90, 2.80, 1.10, 2.90, 1.60, 4, 0.95
    ),
    "SOIC-8": PackageDefinition(
        "SOIC-8", "ic", 4.90, 6.00, 1.50, 4.90, 3.90, 8, 1.27
    ),
    "TSSOP-8": PackageDefinition(
        "TSSOP-8", "ic", 3.00, 6.40, 1.10, 3.00, 4.40, 8, 0.65
    ),
}

SUPPORTED_PACKAGES = (
    "SMD01005",
    "SMD0201",
    "SMD0402",
    "SMD0603",
    "SMD0805",
    "SMD1206",
    "SOT-23",
    "SOT-143",
    "MELF-2012",
    "MELF-3514",
    "SOIC-8",
    "TSSOP-8",
    "LED-0603",
    "LED-0805",
    "LED-1206",
)


def normalize_package(package):
    return str(package or "").strip().upper()


def get_package_definition(package):
    return PACKAGE_DEFINITIONS.get(normalize_package(package))


def component_body_color(value):
    text = "".join(str(value or "").upper().split())
    return COMPONENT_CAPACITOR_COLOR if text.endswith("F") else COMPONENT_BODY_COLOR


def feeder_tape_color(package):
    return (
        FEEDER_LED_TAPE_COLOR
        if normalize_package(package).startswith("LED-")
        else FEEDER_TAPE_COLOR
    )


def _box_part(x, y, z, length, width, height, color, role="body"):
    return {
        "kind": "box",
        "center": (x, y, z),
        "size": (length, width, height),
        "color": color,
        "role": role,
    }


def _cylinder_x_part(x, y, z, length, diameter, color, role="body"):
    return {
        "kind": "cylinder_x",
        "center": (x, y, z),
        "size": (length, diameter, diameter),
        "color": color,
        "role": role,
    }


def _chip_parts(spec, led=False):
    terminal = min(spec.length * 0.22, spec.width * 0.32)
    body_length = max(0.05, spec.length - 2.0 * terminal)
    parts = [
        _box_part(0.0, 0.0, spec.height / 2.0, body_length, spec.width, spec.height,
                  COMPONENT_LED_COLOR if led else COMPONENT_BODY_COLOR),
        _box_part(-(spec.length - terminal) / 2.0, 0.0, spec.height * 0.43,
                  terminal, spec.width, spec.height * 0.86, COMPONENT_TERMINAL_COLOR, "terminal"),
        _box_part((spec.length - terminal) / 2.0, 0.0, spec.height * 0.43,
                  terminal, spec.width, spec.height * 0.86, COMPONENT_TERMINAL_COLOR, "terminal"),
    ]
    if led:
        parts.append(_box_part(0.0, 0.0, spec.height + 0.04, body_length * 0.55,
                               spec.width * 0.55, 0.08, COMPONENT_LED_LENS_COLOR, "lens"))
    return parts


def _melf_parts(spec):
    cap_length = min(spec.length * 0.18, 0.45)
    body_length = spec.length - 2.0 * cap_length
    radius = spec.width / 2.0
    return [
        _cylinder_x_part(0.0, 0.0, radius, body_length, spec.width, COMPONENT_BODY_COLOR),
        _cylinder_x_part(-(spec.length - cap_length) / 2.0, 0.0, radius,
                         cap_length, spec.width, COMPONENT_TERMINAL_COLOR, "terminal"),
        _cylinder_x_part((spec.length - cap_length) / 2.0, 0.0, radius,
                         cap_length, spec.width, COMPONENT_TERMINAL_COLOR, "terminal"),
    ]


def _lead_parts(spec):
    parts = [_box_part(0.0, 0.0, spec.height / 2.0, spec.body_length,
                       spec.body_width, spec.height, COMPONENT_BODY_COLOR)]
    lead_length = max(0.12, (spec.width - spec.body_width) / 2.0)
    lead_width = min(0.45, spec.pitch * 0.48)
    lead_height = min(0.18, spec.height * 0.18)
    per_side = spec.pins // 2
    if spec.family == "sot" and spec.pins == 3:
        side_positions = ((-1, (-spec.pitch / 2.0, spec.pitch / 2.0)), (1, (0.0,)))
    else:
        start = -spec.pitch * (per_side - 1) / 2.0
        positions = tuple(start + i * spec.pitch for i in range(per_side))
        side_positions = ((-1, positions), (1, positions))
    for side, x_positions in side_positions:
        y = side * (spec.body_width / 2.0 + lead_length / 2.0)
        for x in x_positions:
            parts.append(_box_part(x, y, lead_height / 2.0, lead_width,
                                   lead_length, lead_height, COMPONENT_TERMINAL_COLOR, "terminal"))
    return parts


def component_parts_mm(package):
    spec = get_package_definition(package)
    if spec is None:
        return []
    if spec.family == "chip":
        return _chip_parts(spec)
    if spec.family == "led":
        return _chip_parts(spec, led=True)
    if spec.family == "melf":
        return _melf_parts(spec)
    return _lead_parts(spec)


def _box_mesh(length, width, height):
    hx, hy = length / 2.0, width / 2.0
    vertices = np.array([
        [-hx, -hy, 0.0], [hx, -hy, 0.0], [hx, hy, 0.0], [-hx, hy, 0.0],
        [-hx, -hy, height], [hx, -hy, height], [hx, hy, height], [-hx, hy, height],
    ], dtype=float)
    faces = np.array([
        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
    ], dtype=int)
    return vertices, _orient_faces_outward(vertices, faces)


def _orient_faces_outward(vertices, faces):
    vertices = np.asarray(vertices, dtype=float)
    result = np.asarray(faces, dtype=int).copy()
    center = vertices.mean(axis=0)
    for index, (a, b, c) in enumerate(result):
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        normal = np.cross(pb - pa, pc - pa)
        face_center = (pa + pb + pc) / 3.0
        if np.dot(normal, face_center - center) < 0.0:
            result[index] = (a, c, b)
    return result


def _cylinder_x_mesh(length, diameter_y, diameter_z=None, cols=24):
    radius_y = diameter_y / 2.0
    radius_z = (diameter_z if diameter_z is not None else diameter_y) / 2.0
    vertices = []
    for x in (-length / 2.0, length / 2.0):
        for idx in range(cols):
            angle = 2.0 * math.pi * idx / cols
            vertices.append(
                (x, math.cos(angle) * radius_y, math.sin(angle) * radius_z)
            )
    left_center = len(vertices)
    vertices.append((-length / 2.0, 0.0, 0.0))
    right_center = len(vertices)
    vertices.append((length / 2.0, 0.0, 0.0))
    faces = []
    for idx in range(cols):
        nxt = (idx + 1) % cols
        faces.extend(((idx, nxt, cols + nxt), (idx, cols + nxt, cols + idx)))
        faces.append((left_center, nxt, idx))
        faces.append((right_center, cols + idx, cols + nxt))
    vertices = np.asarray(vertices, dtype=float)
    return vertices, _orient_faces_outward(vertices, faces)


def build_component_meshes(
    package,
    scale_x=1.0,
    scale_y=1.0,
    value=None,
    rotation_degrees=0.0,
):
    """Build local component meshes in JPmm X/Y and physical-mm Z units."""
    sx = abs(float(scale_x or 1.0))
    sy = abs(float(scale_y or 1.0))
    meshes = []
    for part in component_parts_mm(package):
        px, py, pz = part["center"]
        length, width, height = part["size"]
        if part["kind"] == "cylinder_x":
            vertices, faces = _cylinder_x_mesh(length, width, height)
            z_offset = pz
        else:
            vertices, faces = _box_mesh(length, width, height)
            z_offset = pz - height / 2.0
        vertices[:, 0] += px
        vertices[:, 1] += py
        vertices[:, 2] += z_offset
        if rotation_degrees:
            vertices = rotate_mesh_z(vertices, rotation_degrees)
        vertices[:, 0] *= sx
        vertices[:, 1] *= sy
        role = part.get("role", "body")
        color = part["color"]
        if normalize_package(package).startswith("LED-"):
            if role == "body":
                color = COMPONENT_LED_COLOR
            elif role == "lens":
                color = COMPONENT_LED_LENS_COLOR
        elif role == "body":
            color = component_body_color(value)
        meshes.append((vertices, faces, color))
    return meshes


def rotate_mesh_z(vertices, degrees):
    angle = math.radians(float(degrees or 0.0))
    cosine, sine = math.cos(angle), math.sin(angle)
    result = np.asarray(vertices, dtype=float).copy()
    x = result[:, 0].copy()
    y = result[:, 1].copy()
    result[:, 0] = x * cosine - y * sine
    result[:, 1] = x * sine + y * cosine
    return result


def pcb_component_rotation(rotation_deg, board_rotation_deg=180.0):
    """Map PnP/Gerber rotation into the scene's (-Y, +X) board axes."""
    return float(rotation_deg or 0.0) + 90.0 + float(board_rotation_deg or 0.0)

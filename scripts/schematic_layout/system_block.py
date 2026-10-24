"""Audit the System_block cover page: labelled flow arrows, a visible isolation
boundary that crosses no block, and no line that ends in the void.

The cover is editable graphics (``sheet`` blocks, ``polyline`` lines, ``text``),
never wires. The audit reads those nodes directly; it does not qualify stroke
styles (the geometry gate covers only default strokes) and it establishes no
electrical fact. A line is the boundary when its label is 隔离/隔离边界/isolation, alone or
followed by a space or colon and its rating ("隔离边界 4kV"), or when it is dashed;
a flow line whose name merely contains the word ("隔离电源") stays a flow line.
"""

import math
import re

from .geometry import Box
from .routing import segment_hits_box
from .sexpr import all_nodes, first

TOUCH_MM = 2.6        # a line end within one grid step of a block edge, arrowhead or line is attached
TEXT_NEAR_MM = 6.0    # a text anchor this close to a line labels it
HEAD_MAX_MM = 4.0     # arrowhead legs are shorter than this
BOUNDARY_LABEL = re.compile(r"^(隔离边界|隔离|isolation boundary|isolation barrier|isolation)($|[\s:：,，(（])", re.IGNORECASE)
DASHED = ("dash", "dot", "dash_dot", "dash_dot_dot")


def _points(node):
    pts = first(node, "pts", [])
    return [(float(p[1]), float(p[2])) for p in pts[1:] if isinstance(p, list) and p[0] == "xy"]


def _dist_point_segment(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    if dx == dy == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _dist_point_polyline(p, points):
    return min(_dist_point_segment(p, a, b) for a, b in zip(points, points[1:]))


def _is_head(points):
    return len(points) == 3 and all(math.hypot(b[0] - a[0], b[1] - a[1]) <= HEAD_MAX_MM
                                    for a, b in zip(points, points[1:]))


def audit_system_block(root):
    """{"status": PASS|FAIL|INSUFFICIENT, "findings": [...], counts...}"""
    sheets = []
    for node in all_nodes(root, "sheet"):
        at, size = first(node, "at"), first(node, "size")
        name = next((str(p[2]) for p in all_nodes(node, "property") if len(p) > 2 and p[1] == "Sheetname"), "?")
        if not at or not size:
            return {"status": "INSUFFICIENT", "findings": [f"sheet {name}: no at/size"], "sheets": 0}
        x, y, w, h = float(at[1]), float(at[2]), float(size[1]), float(size[2])
        sheets.append((name, Box(x, y, x + w, y + h)))
    if not sheets:
        return {"status": "INSUFFICIENT", "findings": ["no sheet blocks on this page"], "sheets": 0}
    texts = [(str(t[1]), (float(first(t, "at")[1]), float(first(t, "at")[2]))) for t in all_nodes(root, "text")
             if first(t, "at")]
    lines, heads = [], []
    for i, node in enumerate(all_nodes(root, "polyline")):
        points = _points(node)
        if len(points) < 2:
            continue
        dashed = str(first(first(node, "stroke", []), "type", [None, None])[1]) in DASHED
        (heads if _is_head(points) else lines).append((i, points, dashed))
    findings = []
    boundaries, arrows = [], []
    for i, points, dashed in lines:
        near = [t for t, at in texts if _dist_point_polyline(at, points) <= TEXT_NEAR_MM]
        if dashed or any(BOUNDARY_LABEL.match(t.strip()) for t in near):
            boundaries.append((i, points, near))
        else:
            arrows.append((i, points, near))
    touched = set()
    for i, points, near in arrows:
        if not near:
            findings.append(f"polyline {i}: flow line carries no text naming the rail or signals it stands for")
        for end in (points[0], points[-1]):
            hit = [name for name, box in sheets if box.expanded(TOUCH_MM).contains_point(*end)]
            joined = (any(math.hypot(end[0] - q[0], end[1] - q[1]) <= TOUCH_MM for _, pts, _ in heads for q in pts)
                      or any(math.hypot(end[0] - q[0], end[1] - q[1]) <= TOUCH_MM
                             for j, pts, _ in arrows if j != i for q in pts))
            touched.update(hit)
            if not hit and not joined:
                findings.append(f"polyline {i}: end {list(end)} touches no block, arrowhead or other line")
        for a, b in zip(points, points[1:]):
            inside = [name for name, box in sheets if segment_hits_box(a, b, box.expanded(-TOUCH_MM))]
            if inside:
                findings.append(f"polyline {i}: runs through block {inside[0]}")
    for i, points, near in boundaries:
        if len(points) > 3:
            findings.append(f"polyline {i}: isolation boundary bends {len(points) - 2} times; keep it straight or one L")
        for a, b in zip(points, points[1:]):
            inside = [name for name, box in sheets if segment_hits_box(a, b, box.expanded(-TOUCH_MM))]
            if inside:
                findings.append(f"polyline {i}: isolation boundary runs through block {inside[0]}")
    for name, _ in sheets:
        if name not in touched:
            findings.append(f"block {name}: no flow line reaches it")
    return {"status": "FAIL" if findings else "PASS", "findings": findings, "sheets": len(sheets),
            "flow_lines": len(arrows), "arrowheads": len(heads), "boundaries": len(boundaries)}

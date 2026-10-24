"""Hierarchical root with the System_block cover, assembled from built pages.

The page scripts draw each page with ``recipes.Sheet``; this module puts those
pages under one root: sheet blocks, child instance paths rewritten to the root
project, and the cover's named flow lines and isolation boundary as editable
graphics (``polyline``/``text``, never wires). Flow lines are derived from the
blocks they join, so both ends land on a block edge and each carries its name.
``write`` runs the System_block audit and raises on FAIL, like ``Sheet.build``.
It establishes no electrical fact; ``verify_schematic.py`` still qualifies the
written project natively.
"""

import json
import shutil
import uuid
from pathlib import Path

from .geometry import Box
from .sexpr import Atom, all_nodes, dump, first, form, parse, set_node
from .native import project_settings
from .system_block import BOUNDARY_LABEL, audit_system_block

GRID = 1.27
HEAD_MM = 2.54        # arrowhead leg along the line (legs stay under system_block.HEAD_MAX_MM)
LABEL_OFFSET_MM = 3.81  # flow name clear of its line's text bounds, inside system_block.TEXT_NEAR_MM
WIDTH = {"power": 0.5, "signal": 0.25}  # energy flow and control links stay visually distinct


def _snap(v):
    return round(round(v / GRID) * GRID, 4)


def _font(*just):
    effects = form("effects", form("font", form("size", 1.27, 1.27)))
    if just:
        effects.append(form("justify", *[Atom(j) for j in just]))
    return effects


class Root:
    """``Root(project, ...)``, then ``page`` per child, ``flow`` per link, ``isolation``, ``write``."""

    def __init__(self, project, paper="A4", date="", rev="", company=None):
        self.project, self.paper, self.date, self.rev = project, paper, date, rev
        self.company = project if company is None else company
        self.root_uuid = self._uid("root")
        self.pages, self.items = [], []

    def _uid(self, key):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "asg-root:" + self.project + ":" + key))

    def page(self, name, sheet, at, size=(76.2, 30.48), note=None):
        """A child page: ``sheet`` is the root returned by ``Sheet.build`` or a ``.kicad_sch`` path."""
        if any(p["name"] == name for p in self.pages):
            raise ValueError(f"Page {name} added twice")
        if isinstance(sheet, (str, Path)):
            sheet = parse(Path(sheet).read_text(encoding="utf-8"))
        x, y = at
        box = Box(x, y, x + size[0], y + size[1])
        for p in self.pages:
            if p["box"].overlaps(box, gap_mm=GRID * 4):
                raise ValueError(f"Block {name} is closer than 5.08 mm to block {p['name']}")
        self.pages.append({"name": name, "sheet": sheet, "at": (x, y), "size": size, "box": box, "note": note})
        return box

    def _box(self, name):
        for p in self.pages:
            if p["name"] == name:
                return p["box"]
        raise ValueError(f"Unknown page {name}; add it with page() first")

    @staticmethod
    def _edge(box, toward):
        """Point on ``box``'s edge from which an axis-aligned leg reaches ``toward``."""
        tx, ty = toward
        if box.x_min < tx < box.x_max and not box.y_min <= ty <= box.y_max:
            return (tx, box.y_max if ty > box.y_max else box.y_min)
        if box.y_min < ty < box.y_max and not box.x_min <= tx <= box.x_max:
            return (box.x_max if tx > box.x_max else box.x_min, ty)
        raise ValueError(f"{toward} is not straight above, below or beside the block; add a via point")

    def flow(self, label, source, target, kind="power", via=(), label_at=None):
        """Named flow line from block ``source`` to block ``target`` with an arrowhead at the target.

        Without ``via`` the blocks must share a row or a column band; the line
        runs straight through the middle of that band. ``via`` points make an
        orthogonal route; each leg must be horizontal or vertical.
        """
        if kind not in WIDTH:
            raise ValueError(f"Flow kind must be one of {sorted(WIDTH)}")
        a, b = self._box(source), self._box(target)
        if via:
            via = [(_snap(x), _snap(y)) for x, y in via]
            points = [self._edge(a, via[0]), *via, self._edge(b, via[-1])]
        else:
            y0, y1 = max(a.y_min, b.y_min), min(a.y_max, b.y_max)
            x0, x1 = max(a.x_min, b.x_min), min(a.x_max, b.x_max)
            if y1 - y0 > 2 * GRID and (a.x_max < b.x_min or b.x_max < a.x_min):
                y = _snap((y0 + y1) / 2)
                points = [(a.x_max, y), (b.x_min, y)] if a.x_max < b.x_min else [(a.x_min, y), (b.x_max, y)]
            elif x1 - x0 > 2 * GRID and (a.y_max < b.y_min or b.y_max < a.y_min):
                x = _snap((x0 + x1) / 2)
                points = [(x, a.y_max), (x, b.y_min)] if a.y_max < b.y_min else [(x, a.y_min), (x, b.y_max)]
            else:
                raise ValueError(f"{source} and {target} share no row or column; give via points")
        for p, q in zip(points, points[1:]):
            if p[0] != q[0] and p[1] != q[1]:
                raise ValueError(f"Flow {label}: leg {p}-{q} is neither horizontal nor vertical")
        if label_at is None:
            p, q = max(zip(points, points[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            label_at, just = ((mid[0], mid[1] - LABEL_OFFSET_MM), ()) if p[1] == q[1] \
                else ((mid[0] + LABEL_OFFSET_MM, mid[1]), ("left",))
        else:
            just = ()
        self.items.append(("flow", label, points, WIDTH[kind], label_at, just))

    def isolation(self, x=None, y=None, label="隔离", span=None):
        """Straight isolation boundary at ``x`` (vertical) or ``y`` (horizontal) across the blocks."""
        if (x is None) == (y is None):
            raise ValueError("Give exactly one of x or y")
        if not BOUNDARY_LABEL.match(label.strip()):
            raise ValueError("Isolation label must start with 隔离 or isolation, e.g. '隔离 1500 Vrms'")
        boxes = [p["box"] for p in self.pages]
        if not boxes:
            raise ValueError("Add the pages before the isolation boundary")
        lo, hi = span or ((min(b.y_min for b in boxes) - 5 * GRID, max(b.y_max for b in boxes) + 5 * GRID) if x is not None
                          else (min(b.x_min for b in boxes) - 5 * GRID, max(b.x_max for b in boxes) + 5 * GRID))
        points = [(x, lo), (x, hi)] if x is not None else [(lo, y), (hi, y)]
        label_at = (x - GRID, lo + 2 * GRID) if x is not None else (lo + 2 * GRID, y - GRID)
        self.items.append(("boundary", label, points, 0.35, label_at, ("right",) if x is not None else ("left",)))

    def text(self, text, at):
        """Note on the cover (power domains, return names, conditions)."""
        self.items.append(("text", text, None, None, at, ()))

    def _cover(self):
        root = form("kicad_sch", form("version", self._version()), form("generator", "asg_root"),
                    form("uuid", self.root_uuid), form("paper", self.paper),
                    form("title_block", form("title", "System_block"), form("date", self.date),
                         form("rev", self.rev), form("company", self.company)),
                    form("lib_symbols"))
        for n, p in enumerate(self.pages, 2):
            (x, y), (w, h) = p["at"], p["size"]
            root.append(form("sheet", form("at", x, y), form("size", w, h),
                             form("stroke", form("width", 0.254), form("type", Atom("default"))),
                             form("fill", form("color", 0, 0, 0, 0)), form("uuid", self._uid("sheet:" + p["name"])),
                             form("property", "Sheetname", p["name"], form("at", x, y - 0.508, 0),
                                  _font("left", "bottom")),
                             form("property", "Sheetfile", p["name"] + ".kicad_sch", form("at", x, y + h + 0.508, 0),
                                  _font("left", "top")),
                             form("instances", form("project", self.project,
                                                    form("path", "/" + self.root_uuid, form("page", str(n)))))))
            if p["note"]:
                root.append(form("text", p["note"], form("at", _snap(x + w / 2), _snap(y + h / 2), 0), _font(),
                                 form("uuid", self._uid("note:" + p["name"]))))
        for k, (kind, label, points, width, at, just) in enumerate(self.items):
            key = f"{kind}:{k}:{label}"
            if points:
                root.append(self._line(points, width, key))
                if kind == "flow":
                    (px, py), (qx, qy) = points[-2], points[-1]
                    dx = (qx > px) - (qx < px)
                    dy = (qy > py) - (qy < py)
                    head = [(qx - dx * HEAD_MM - dy * GRID, qy - dy * HEAD_MM - dx * GRID), (qx, qy),
                            (qx - dx * HEAD_MM + dy * GRID, qy - dy * HEAD_MM + dx * GRID)]
                    root.append(self._line(head, width, key + ":head"))
            root.append(form("text", label, form("at", at[0], at[1], 0), _font(*just), form("uuid", self._uid(key))))
        root.append(form("sheet_instances", form("path", "/", form("page", "1"))))
        return root

    def _line(self, points, width, key):
        return form("polyline", form("pts", *[form("xy", x, y) for x, y in points]),
                    form("stroke", form("width", width), form("type", Atom("default"))), form("uuid", self._uid(key)))

    def _version(self):
        versions = {int(first(p["sheet"], "version")[1]) for p in self.pages if first(p["sheet"], "version")}
        return max(versions) if versions else 20250114

    def _child(self, n, p):
        sid = self._uid("sheet:" + p["name"])
        child = parse(dump(p["sheet"]))
        set_node(child, "uuid", sid)
        set_node(child, "title_block", form("title", p["name"]), form("date", self.date), form("rev", self.rev),
                 form("company", self.company))
        for symbol in all_nodes(child, "symbol"):
            path = first(first(first(symbol, "instances") or [], "project") or [], "path")
            if path is None:
                raise ValueError(f"Page {p['name']}: a symbol has no instance path; build the page with Sheet.build")
            set_node(symbol, "instances", form("project", self.project,
                                               form("path", "/" + self.root_uuid + "/" + sid,
                                                    first(path, "reference"), first(path, "unit"))))
        set_node(child, "sheet_instances", form("path", "/" + self.root_uuid + "/" + sid, form("page", str(n))))
        return child

    def write(self, out_dir, libraries=None):
        """Write root, pages, ``.kicad_pro`` and ``sym-lib-table`` into a new directory.

        ``libraries`` maps a project symbol library nickname to its ``.kicad_sym``
        file, copied next to the root. Returns ``{"root", "system_block"}``.
        """
        if not self.pages:
            raise ValueError("No pages")
        cover = self._cover()
        audit = audit_system_block(cover)
        if audit["status"] != "PASS":
            raise ValueError(f"System_block audit {audit['status']}: {audit['findings']}")
        out = Path(out_dir)
        if out.exists() and any(out.iterdir()):
            raise ValueError(f"{out} is not empty; write into a fresh directory")
        out.mkdir(parents=True, exist_ok=True)
        for n, p in enumerate(self.pages, 2):
            (out / (p["name"] + ".kicad_sch")).write_text(dump(self._child(n, p)) + "\n", encoding="utf-8")
        root_file = out / (self.project + ".kicad_sch")
        root_file.write_text(dump(cover) + "\n", encoding="utf-8")
        (out / (self.project + ".kicad_pro")).write_text(json.dumps(
            {"meta": {"filename": self.project + ".kicad_pro", "version": 1},
             "schematic": {"drawing": {}, "legacy_lib_dir": "", "legacy_lib_list": []},
             "erc": {"erc_exclusions": [], **project_settings()["erc"]}}, indent=2) + "\n", encoding="utf-8")
        libs = []
        for nick, path in sorted((libraries or {}).items()):
            shutil.copy2(path, out / Path(path).name)
            libs.append(f'(lib (name "{nick}") (type "KiCad") (uri "${{KIPRJMOD}}/{Path(path).name}") (options "") (descr ""))')
        if libs:
            (out / "sym-lib-table").write_text("(sym_lib_table (version 7) " + " ".join(libs) + ")\n", encoding="utf-8")
        return {"root": root_file, "system_block": audit}

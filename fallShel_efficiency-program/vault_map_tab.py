import json
import os
from typing import Self
import virtualvaultmap

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QTextEdit, QPushButton, QSplitter, QSizePolicy,
    QGridLayout, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient




# ──────────────────────────────────────────────────────────────────────────────
#   Colour / Style helpers
# ──────────────────────────────────────────────────────────────────────────────

ROOM_COLOURS = {
    # Production rooms
    "Geothermal":  ("#e63946", "#ff6b6b"),   # reds  – Power (Strength)
    "Energy2":     ("#e63946", "#ff6b6b"),
    "WaterPlant":  ("#0077b6", "#48cae4"),   # blues – Water (Perception)
    "Water2":      ("#0077b6", "#48cae4"),
    "Cafeteria":   ("#2d6a4f", "#52b788"),   # greens – Food (Agility)
    "Hydroponic":  ("#2d6a4f", "#52b788"),
    "MedBay":      ("#7b2d8b", "#c77dff"),   # purples – Medbay (Intelligence)
    "ScienceLab":  ("#7b2d8b", "#c77dff"),
    "NukaCola":    ("#9c6b00", "#ffd166"),   # golds  – NukaCola
    # Training rooms
    "Gym":         ("#4a4e69", "#9a8c98"),
    "Armory":      ("#4a4e69", "#9a8c98"),
    "Dojo":        ("#4a4e69", "#9a8c98"),
    "Classroom":   ("#4a4e69", "#9a8c98"),
    # Other
    "Elevator":    ("#1b1b2f", "#4cc9f0"),
    "Living":      ("#1b4332", "#74c69d"),
    "Quarters":    ("#1b4332", "#74c69d"),
}
FALLBACK_COLOUR = ("#1a1a2e", "#4f5d75")

STAT_ICON = {
    "Strength":     "💪",
    "Perception":   "👁",
    "Endurance":    "🛡",
    "Charisma":     "💬",
    "Intelligence": "🧠",
    "Agility":      "⚡",
    "Luck":         "🍀",
}

ROOM_ICON = {
    "Geothermal":  "⚡", "Energy2":   "⚡",
    "WaterPlant":  "💧", "Water2":    "💧",
    "Cafeteria":   "🍽", "Hydroponic":"🌱",
    "MedBay":      "💊", "ScienceLab":"🔬",
    "NukaCola":    "🥤",
    "Gym":         "🏋", "Armory":    "🔫",
    "Dojo":        "🥋", "Classroom": "📚",
    "Elevator":    "🛗",
    "Living":      "🛏", "Quarters":  "🛏",
}

ROOM_STAT_MAP = {
    "Geothermal":  "Strength",
    "Energy2":     "Strength",
    "WaterPlant":  "Perception",
    "Water2":      "Perception",
    "Cafeteria":   "Agility",
    "Hydroponic":  "Agility",
    "MedBay":      "Intelligence",
    "ScienceLab":  "Intelligence",
    "NukaCola":    "Perception",
    "Gym":         "Strength",
    "Armory":      "Strength",
    "Dojo":        "Agility",
    "Classroom":   "Intelligence",
}

ROOM_CODE_REMAP = {
    # Sometimes placementCalc stores abbreviations; normalise here
    "Power":   "Geothermal",
    "Water":   "WaterPlant",
    "Food":    "Cafeteria",
    "Medbay":  "MedBay",
}




ROWS = 25
COLUMNS = 26
CELL_W = 20
CELL_H = 40


# ─────────────────────────────────────────────
# Room cell
# ─────────────────────────────────────────────
class RoomCell(QFrame):
    clicked = Signal(dict)

    def __init__(self, room_data: dict):
        super().__init__()
        self.room_data = room_data
        self._selected = False

        raw_type = room_data.get("room_type", "Room")
        self.room_type = ROOM_CODE_REMAP.get(raw_type, raw_type)
        self._is_elevator = (self.room_type == "Elevator")

        # Resolve colours for this room type
        colours = ROOM_COLOURS.get(self.room_type, FALLBACK_COLOUR)
        self._bg_colour   = colours[0]   # dark base colour
        self._accent_colour = colours[1] # lighter accent

        self.setFixedHeight(CELL_H)
        self.setStyleSheet(self._style())

        # Build a layout so the label sits centred both horizontally and vertically
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Only show the name label for non-Elevator rooms
        if not self._is_elevator:
            label = QLabel(self.room_type, self)
            label.setAlignment(Qt.AlignCenter)
            label.setWordWrap(True)
            label.setStyleSheet(
                "color: white; font-size: 13px; font-weight: bold;"
                " background: transparent;"
            )
            layout.addWidget(label, alignment=Qt.AlignCenter)
        else:
            # Elevator: just show the icon, no text
            icon_lbl = QLabel(ROOM_ICON.get("Elevator", "🛗"), self)
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lbl.setStyleSheet("background: transparent; font-size: 9px;")
            layout.addWidget(icon_lbl, alignment=Qt.AlignCenter)

    def mousePressEvent(self, event):
        # Elevator cells are non-interactive
        if self._is_elevator:
            return
        self.clicked.emit(self.room_data)

    def set_selected(self, state: bool):
        self._selected = state
        self.setStyleSheet(self._style())

    def _style(self):
        if self._selected:
            return (
                f"background: #ffcc00;"
                f" border: 2px solid #ffffff;"
                f" border-radius: 3px;"
            )
        return (
            f"background: {self._bg_colour};"
            f" border: 1px solid {self._accent_colour}55;"
            f" border-radius: 3px;"
        )






# ─────────────────────────────────────────────
# Vault grid widget
# ─────────────────────────────────────────────
class VaultGridWidget(QWidget):

    room_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vault_design = None
        self._cells = []
        self._selected_cell = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        title = QLabel("🏚 VAULT LIVE MAP")
        title.setStyleSheet(
            "background:#111; color:#ffcc00; padding:6px;"
        )
        outer.addWidget(title)

        self.grid = QGridLayout()
        self.grid.setSpacing(1)
        self.grid.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.grid)

        self._build_base_grid()


    def set_vault_design(self, design):
        self.vault_design = design
        self.rebuild()
    # ─────────────────────────────────────────
    def _build_base_grid(self):
        """Create empty grid with placeholders"""

        for r in range(ROWS):
            self.grid.setRowMinimumHeight(r, CELL_H)
            for c in range(COLUMNS):
                self.grid.setColumnMinimumWidth(c, CELL_W)

                placeholder = QFrame()
                placeholder.setStyleSheet(
                    "background:#111111; border:1px solid #222222;"
                )
                self.grid.addWidget(placeholder, r, c)
                self.grid.setColumnStretch(c, 1)
                self.grid.setRowStretch(r, 1)


    # ─────────────────────────────────────────

    @staticmethod
    def _size_str(width_cols: int) -> str:
        """Convert vault_design grid width (columns) to size string used by placementCalc."""
        if width_cols >= 9:
            return "size9"
        if width_cols >= 6:
            return "size6"
        return "size3"

    @staticmethod
    def _lvl_str(room_level) -> str:
        """Normalise a room level value to 'lvlX'."""
        if isinstance(room_level, str) and room_level.startswith("lvl"):
            return room_level
        try:
            v = int(room_level)
            if v in (1, 2, 3):
                return f"lvl{v}"
        except (TypeError, ValueError):
            pass
        return "lvl1"

    def rebuild(self, room_assignments=None, dweller_assignments=None):
        """Rebuild the grid, matching vault_design rooms to optimization data using
        the same (type, level, size, ordinal-number) key scheme as placementCalc."""

        # ── Remove old room cells ────────────────────────────────────────────
        for cell in self._cells:
            cell.deleteLater()
        self._cells.clear()

        if not self.vault_design:
            print("WARNING: No vault_design available")
            return

        # ── Build a fast lookup: canonical_room_key -> room_assignment dict ──
        # room_assignments keys look like "Geothermal_lvl3_size3_1"
        opt_by_key = {}
        if room_assignments:
            for ra_key, ra_data in room_assignments.items():
                opt_by_key[ra_key] = ra_data

        # ── Build a fast lookup: canonical_room_key -> [full dweller dicts] ──
        # Each dweller's assigned_room has {room_type, room_level, room_size, room_number}
        dwellers_by_room = {}   # canonical_key -> [dweller_entry, ...]
        if dweller_assignments:
            for dw in dweller_assignments:
                ar = dw.get("assigned_room")
                if not ar:
                    continue
                key = (
                    f"{ar['room_type']}"
                    f"_{self._lvl_str(ar['room_level'])}"
                    f"_{ar['room_size']}"
                    f"_{ar['room_number']}"
                )
                dwellers_by_room.setdefault(key, []).append(dw)

        # ── Assign ordinal numbers to vault_design rooms ─────────────────────
        # placementCalc numbers rooms with the same (type, level, size) in the
        # order they are encountered scanning left-to-right, top-to-bottom.
        # vault_design is already in that order, so we just count.
        ordinal_counter = {}   # (type, lvl_str, size_str) -> running count

        # Sort vault_design by (row, col) to guarantee scan order
        sorted_design = sorted(self.vault_design, key=lambda r: (r.get("row", 0), r.get("col", 0)))

        for room in sorted_design:
            raw_type  = room.get("type", "Unknown")
            room_type = ROOM_CODE_REMAP.get(raw_type, raw_type)
            row       = room.get("row", 0)
            col       = room.get("col", 0)
            width     = room.get("width", 1)

            # Skip non-optimizable rooms (Elevator, Living, etc.)
            lvl_str  = self._lvl_str(room.get("level", 1))
            size_str = self._size_str(width)

            base = (room_type, lvl_str, size_str)
            ordinal_counter[base] = ordinal_counter.get(base, 0) + 1
            ordinal = str(ordinal_counter[base])

            # e.g. "Geothermal_lvl3_size3_1"
            canonical_key = f"{room_type}_{lvl_str}_{size_str}_{ordinal}"

            # ── Fetch matching optimization data ─────────────────────────────
            opt_data = opt_by_key.get(canonical_key)
            full_dwellers = dwellers_by_room.get(canonical_key, [])

            if opt_data:
                room_data = opt_data.copy()
                room_data["row"]          = row
                room_data["col"]          = col
                room_data["canonical_key"] = canonical_key
                room_data["dwellers_full"] = full_dwellers
                if "size" not in room_data:
                    room_data["size"] = size_str
            else:
                room_data = {
                    "room_type":    room_type,
                    "row":          row,
                    "col":          col,
                    "size":         size_str,
                    "level":        lvl_str,
                    "number":       ordinal,
                    "canonical_key": canonical_key,
                    "dwellers":     [],
                    "dwellers_full": full_dwellers,
                }

            cell = RoomCell(room_data)
            cell.clicked.connect(self._on_room_clicked)
            self.grid.addWidget(cell, row, col, 1, width)
            self._cells.append(cell)

        print(f"DEBUG: Created {len(self._cells)} room cells")

    def _convert_vault_design_to_assignments(self):
        """Convert old vault_design format to room_assignments format"""
        if not self.vault_design:
            return {}
        
        assignments = {}
        for i, room in enumerate(self.vault_design):
            room_key = f"room_{i}"
            assignments[room_key] = {
                "room_type": room.get("type", "Unknown"),
                "row": room.get("row", 0),
                "col": room.get("col", 0),
                "size": room.get("width", 1),
                "number": i
            }
        return assignments




    # ─────────────────────────────────────────
    def _on_room_clicked(self, room_data: dict):
        if self._selected_cell:
            self._selected_cell.set_selected(False)

        for cell in self._cells:
            if cell.room_data is room_data:
                cell.set_selected(True)
                self._selected_cell = cell
                break

        self.room_selected.emit(room_data)









# ──────────────────────────────────────────────────────────────────────────────
#   Detail panel (right side)
# ──────────────────────────────────────────────────────────────────────────────

class RoomDetailPanel(QWidget):
    """Displays detailed information about the selected room."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        self._header = QLabel("SELECT A ROOM")
        self._header.setStyleSheet(
            "color: #ffcc00; font-size: 14px; font-weight: bold;"
            " font-family: 'Consolas'; padding: 6px;"
            " border-bottom: 2px solid #00ff00;"
            " background-color: #111111;"
        )
        self._header.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #00ff00; background: #1a1a1a; }"
            "QScrollBar:vertical { background: #2a2a2a; width: 10px; }"
            "QScrollBar::handle:vertical { background: #00ff00; }"
        )
        self._content = QLabel()
        self._content.setWordWrap(True)
        self._content.setTextFormat(Qt.RichText)
        self._content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._content.setStyleSheet(
            "color: #cccccc; font-size: 15px; background: transparent;"
            " padding: 8px; font-family: 'Consolas';"
        )
        self._content.setText(
            "<span style='color:#444; font-size: 11px;'>Click any room on the map to see<br>"
            "dweller assignments and room details.</span>"
        )
        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

    # ── public API ────────────────────────────────────────────────────────────

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_room_key(room_info: dict) -> str:
        """Turn a previous_room / assigned_room dict into a readable label.
        Keys: room_type, room_level, room_size, room_number."""
        if not room_info:
            return "?"
        rt  = room_info.get("room_type", "?")
        lvl = room_info.get("room_level", "?")
        sz  = room_info.get("room_size", "?")
        num = room_info.get("room_number", "?")
        # Normalise "lvl3" → "Lv.3", "size6" → "×6"
        lvl_disp = lvl.replace("lvl", "Lv.") if isinstance(lvl, str) else f"Lv.{lvl}"
        sz_disp  = sz.replace("size", "×")   if isinstance(sz, str)  else f"×{sz}"
        return f"{rt} {lvl_disp} {sz_disp} #{num}"

    # ── public API ────────────────────────────────────────────────────────────

    def show_room(self, room_data: dict):
        raw_type  = room_data.get("room_type", "?")
        disp_type = ROOM_CODE_REMAP.get(raw_type, raw_type)
        level     = room_data.get("level", "?")
        size      = room_data.get("size", "?")
        number    = room_data.get("number", "?")
        colours   = ROOM_COLOURS.get(disp_type, FALLBACK_COLOUR)
        accent    = colours[1]
        icon      = ROOM_ICON.get(disp_type, "🏠")
        req_stat  = ROOM_STAT_MAP.get(disp_type, "–")
        stat_icon = STAT_ICON.get(req_stat, "")

        prod_now    = room_data.get("production_time")
        prod_before = room_data.get("before_balance_time")
        prod_init   = room_data.get("initial_time")

        # Dweller list – prefer full detail, fall back to light list
        dwellers_full = room_data.get("dwellers_full", [])
        if not dwellers_full:
            dwellers_full = [
                {"name": d.get("name", f"Dweller {d.get('id','')}"), "id": d.get("id", "?")}
                for d in room_data.get("dwellers", [])
            ]

        # Separate moved vs stayed dwellers for summary counts
        moved_count = sum(1 for dw in dwellers_full if dw.get("dweller_moved"))

        # ── Header ──────────────────────────────────────────────────────────
        lvl_disp = level.replace("lvl", "Lv.") if isinstance(level, str) else f"Lv.{level}"
        sz_disp  = size.replace("size", "×")   if isinstance(size, str)  else f"×{size}"
        self._header.setText(f"{icon}  {disp_type.upper()}  —  {lvl_disp}  {sz_disp}  #{number}")
        self._header.setStyleSheet(
            f"color: {accent}; font-size: 17px; font-weight: bold;"
            " font-family: 'Consolas'; padding: 6px;"
            f" border-bottom: 2px solid {accent};"
            " background-color: #111111;"
        )

        # ── HTML helpers ─────────────────────────────────────────────────────
        def kv(k, v, vcolour="#ffffff"):
            return (
                f"<tr>"
                f"<td style='color:#888; padding:2px 8px 2px 0; white-space:nowrap;'>{k}</td>"
                f"<td style='color:{vcolour}; padding:2px 0;'>{v}</td>"
                f"</tr>"
            )

        def section_hdr(label):
            return (
                f"<div style='margin-top:14px; color:{accent}; font-weight:bold;"
                f" border-bottom:1px solid {accent}44; padding-bottom:3px;'>"
                f"{label}</div>"
            )

        # ── Room info table ──────────────────────────────────────────────────
        html = f"<table style='border-collapse:collapse; width:100%;'>"
        html += kv("Room type",  f"<b>{disp_type}</b>")
        html += kv("Level / size", f"{lvl_disp}  {sz_disp}")
        html += kv("Room #",     number)
        html += kv("Key stat",   f"{stat_icon} <b>{req_stat}</b>", accent)

        if prod_init is not None:
            html += kv("Initial time",    f"{prod_init:.1f}s",   "#ff6b6b")
        if prod_before is not None:
            html += kv("After balancing", f"{prod_before:.1f}s", "#feca57")
        if prod_now is not None:
            delta_str = ""
            if prod_init and prod_init > 0:
                delta = prod_init - prod_now
                pct   = (delta / prod_init) * 100
                col   = "#1dd1a1" if delta >= 0 else "#ff6b6b"
                sign  = "▼" if delta >= 0 else "▲"
                delta_str = (
                    f"&nbsp;<span style='color:{col};'>"
                    f"{sign}{abs(delta):.1f}s ({abs(pct):.0f}%)</span>"
                )
            html += kv("With outfits", f"<b style='color:#ffd166;'>{prod_now:.1f}s</b>{delta_str}")
        html += "</table>"

        # ── Dweller movements summary ────────────────────────────────────────
        total = len(dwellers_full)
        stayed = total - moved_count
        html += section_hdr(f"👤 DWELLERS  ({total} assigned  •  {moved_count} moved  •  {stayed} stayed)")

        if not dwellers_full:
            html += "<p style='color:#555; font-style:italic;'>No dwellers assigned</p>"
        else:
            # Sort: moved dwellers first, then stayed
            sorted_dwellers = sorted(
                dwellers_full,
                key=lambda d: (0 if d.get("dweller_moved") else 1, d.get("name", ""))
            )

            for dw in sorted_dwellers:
                name      = dw.get("name", "Unknown")
                dw_id     = dw.get("id", "?")
                all_stats = dw.get("all_stats", {})
                moved     = dw.get("dweller_moved")       # {"from": "...", "to": "..."}
                prev_rm   = dw.get("previous_room")       # {room_type, room_level, room_size, room_number}
                cur_rm    = dw.get("assigned_room", {})
                outfit    = dw.get("outfit")

                # Card border colour: amber if moved, subtle accent if stayed
                border_col = "#feca57" if moved else f"{accent}33"
                bg_col     = "#241f10" if moved else "#1a1a2e"

                html += (
                    f"<div style='background:{bg_col}; border:1px solid {border_col};"
                    f" border-radius:5px; padding:7px 9px; margin:5px 0;'>"
                )

                # ── Name row ────────────────────────────────────────────────
                if moved:
                    badge = (
                        "<span style='background:#feca5733; border:1px solid #feca57;"
                        " padding:1px 6px; border-radius:3px; color:#feca57;"
                        " font-size:13px; font-weight:bold;'>MOVED</span>"
                    )
                else:
                    badge = (
                        f"<span style='background:{accent}22; border:1px solid {accent}55;"
                        f" padding:1px 6px; border-radius:3px; color:{accent};"
                        f" font-size:13px;'>STAYED</span>"
                    )

                html += (
                    f"<div style='margin-bottom:4px;'>"
                    f"<b style='color:#ffcc00; font-size:11px;'>{name}</b>&nbsp;"
                    f"<span style='color:#555; font-size:13px;'>#{dw_id}</span>&nbsp;"
                    f"{badge}</div>"
                )

                # ── Movement row ─────────────────────────────────────────────
                if moved:
                    from_key = moved.get("from", "?")
                    to_key   = moved.get("to",   "?")

                    # Parse the raw "Type_lvlX_sizeY_N" string into a friendlier label
                    def _parse_key(k):
                        parts = k.split("_") if k != "?" else []
                        if len(parts) == 4:
                            rt, lvl, sz, num = parts
                            return f"{rt} {lvl.replace('lvl','Lv.')} {sz.replace('size','×')} #{num}"
                        return k

                    from_lbl = _parse_key(from_key)
                    to_lbl   = _parse_key(to_key)

                    html += (
                        f"<div style='background:#1a1008; border-left:3px solid #ff6b6b;"
                        f" padding:3px 6px; margin:3px 0; font-size:14px; border-radius:2px;'>"
                        f"<span style='color:#ff6b6b;'>⬅ WAS IN: </span>"
                        f"<span style='color:#ffaa88;'>{from_lbl}</span>"
                        f"</div>"
                        f"<div style='background:#081a10; border-left:3px solid #1dd1a1;"
                        f" padding:3px 6px; margin:3px 0; font-size:14px; border-radius:2px;'>"
                        f"<span style='color:#1dd1a1;'>➜ MOVED TO: </span>"
                        f"<span style='color:#88ffcc;'>{to_lbl}</span>"
                        f"</div>"
                    )
                else:
                    # Stayed – show current room as confirmation
                    cur_lbl = self._fmt_room_key(cur_rm) if cur_rm else "—"
                    html += (
                        f"<div style='font-size:14px; color:#555; margin:2px 0;'>"
                        f"📍 Remained in {cur_lbl}</div>"
                    )

                # ── S.P.E.C.I.A.L mini-bar ──────────────────────────────────
                if all_stats:
                    stat_order = ["Strength","Perception","Endurance","Charisma","Intelligence","Agility","Luck"]
                    abbrev     = ["S","P","E","C","I","A","L"]
                    html += "<div style='margin:5px 0 2px; font-size:14px;'>"
                    for s, a in zip(stat_order, abbrev):
                        v   = all_stats.get(s, 0)
                        col = accent if s == req_stat else "#555"
                        fw  = "bold" if s == req_stat else "normal"
                        html += (
                            f"<span style='color:{col}; font-weight:{fw};"
                            f" margin-right:5px;'>{a}:{v}</span>"
                        )
                    html += "</div>"

                # ── Outfit ───────────────────────────────────────────────────
                if outfit:
                    oname    = outfit.get("outfit_name", "?")
                    bonuses  = []
                    for field, label in [
                        ("strength_bonus","S"), ("perception_bonus","P"),
                        ("agility_bonus","A"),  ("intelligence_bonus","I"),
                    ]:
                        val = outfit.get(field, 0)
                        if val:
                            bonuses.append(f"{label}+{val}")
                    bonus_str = "  ".join(bonuses) if bonuses else "no bonuses"
                    prev_owner = outfit.get("previous_owner")
                    prev_str   = ""
                    if prev_owner:
                        pname = prev_owner.get("dweller_name", "?")
                        prev_str = f"  <span style='color:#888;'>(was {pname})</span>"
                    html += (
                        f"<div style='font-size:14px; color:#c77dff; margin-top:4px;'>"
                        f"👔 {oname}  [{bonus_str}]{prev_str}</div>"
                    )

                html += "</div>"  # end dweller card

        # ── Recommended composition ──────────────────────────────────────────
        html += (
            f"<div style='margin-top:14px; color:{accent}; font-weight:bold;"
            f" border-bottom:1px solid {accent}; padding-bottom:4px;'>"
            f"🎯 IDEAL ASSIGNMENT</div>"
        )
        # Derive capacity from size string ("size3"->2, "size6"->4, "size9"->6) or int
        _SIZE_CAP = {"size3": 2, "size6": 4, "size9": 6}
        if isinstance(size, str) and size in _SIZE_CAP:
            capacity = _SIZE_CAP[size]
        else:
            try:
                capacity = int(size) * 2
            except (ValueError, TypeError):
                capacity = 2
        html += (
            f"<p style='color:#aaaaaa; margin:6px 0;'>"
            f"This room requires <b style='color:{accent};'>{req_stat}</b> "
            f"({stat_icon}).  Best capacity: <b style='color:#ffd166;'>"
            f"{capacity} dwellers</b>.</p>"
        )
        if dwellers_full:
            # Rank dwellers by their key stat value
            ranked = sorted(
                [d for d in dwellers_full if d.get("all_stats")],
                key=lambda d: d["all_stats"].get(req_stat, 0),
                reverse=True,
            )
            if ranked:
                html += "<p style='color:#888; font-size:14px; margin:2px 0;'>Ranked by key stat:</p>"
                for rank, dw in enumerate(ranked, 1):
                    v = dw["all_stats"].get(req_stat, 0)
                    col = "#ffd700" if rank == 1 else "#aaaaaa"
                    html += (
                        f"<div style='font-size:14px; color:{col};'>"
                        f"#{rank}  {dw.get('name','?')}  —  {req_stat}: {v}</div>"
                    )

        html += "</p>"

        self._content.setText(html)


# ──────────────────────────────────────────────────────────────────────────────
#   VaultMapTab – the complete tab widget
# ──────────────────────────────────────────────────────────────────────────────

class VaultMapTab(QWidget):
    """
    Full tab: scrollable vault grid on the left, room detail panel on the right.
    Call update_from_results(suggestions_dict) after each optimization cycle.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_results: dict | None = None
        self._vault_name: str | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Tool bar ────────────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #111111; border-bottom: 1px solid #00ff00;")
        toolbar.setFixedHeight(38)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(12)

        title_lbl = QLabel("🗺️  LIVE VAULT MAP")
        title_lbl.setStyleSheet(
            "color: #ffcc00; font-size: 13px; font-weight: bold;"
            " font-family: 'Consolas'; background: transparent;"
        )
        tb_layout.addWidget(title_lbl)

        self._cycle_lbl = QLabel("No data yet")
        self._cycle_lbl.setStyleSheet(
            "color: #555; font-size: 10px; background: transparent;"
        )
        tb_layout.addWidget(self._cycle_lbl)

        tb_layout.addStretch()

        refresh_btn = QPushButton("⟳ Refresh from file")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setStyleSheet(
            "QPushButton { background:#222; border:1px solid #00ff00; color:#00ff00;"
            " font-size:10px; padding:0 10px; border-radius:3px; }"
            "QPushButton:hover { background:#00ff00; color:#000; }"
        )
        refresh_btn.clicked.connect(self._refresh_from_file)
        tb_layout.addWidget(refresh_btn)

        main_layout.addWidget(toolbar)




        # ── Splitter: vault grid (left) | detail panel (right) ──────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #00ff00; width: 2px; }"
        )





        # Left – scrollable vault grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: #0d0d0d; }"
            "QScrollBar:vertical   { background:#1a1a1a; width:12px; }"
            "QScrollBar::handle:vertical   { background:#00ff00; min-height:20px; }"
            "QScrollBar:horizontal { background:#1a1a1a; height:12px; }"
            "QScrollBar::handle:horizontal { background:#00ff00; min-width:20px; }"
        )

        self._grid = VaultGridWidget()
        scroll.setWidget(self._grid)
        self._grid.room_selected.connect(self._on_room_selected)

        # Right – detail panel
        self._detail = RoomDetailPanel()

        splitter.addWidget(scroll)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter, 1)

    # ── public API ────────────────────────────────────────────────────────────

    def set_vault_name(self, vault_name: str):
        """Call this when a vault is selected, so the tab knows where to read files."""
        self._vault_name = vault_name
        # Try to load vault design from virtualvaultmap module
        try:
            if hasattr(virtualvaultmap, 'get_vault_design'):
                vault_design = virtualvaultmap.get_vault_design(vault_name)
                self._grid.set_vault_design(vault_design)
            else:
                print(f"WARNING: virtualvaultmap has no get_vault_design function")
        except Exception as e:
            print(f"WARNING: Could not load vault design: {e}")
    
    def set_vault_design(self, vault_design):
        """Set the vault design directly."""
        self._grid.set_vault_design(vault_design)

    def update_from_results(self, suggestions: dict):
        """
        Slot connected to OptimizationThread.dweller_suggestions signal.
        `suggestions` is the raw dict from the optimization_results JSON.
        """
        if not suggestions:
            return

        room_assignments   = suggestions.get("room_assignments", {})
        dweller_assignments = suggestions.get("dweller_assignments", [])

        self._last_results = suggestions
        self._grid.rebuild(room_assignments, dweller_assignments)
        
        # Update status message
        total_rooms = len(self._grid._cells)
        opt_rooms = len(room_assignments) if room_assignments else 0
        self._cycle_lbl.setText(
            f"Updated  —  {total_rooms} total rooms  •  {opt_rooms} optimized  •  {len(dweller_assignments)} dwellers"
        )
        self._cycle_lbl.setStyleSheet(
            "color: #1dd1a1; font-size: 10px; background: transparent;"
        )

    # ── private ───────────────────────────────────────────────────────────────

    def _on_room_selected(self, room_data: dict):
        self._detail.show_room(room_data)

    def _refresh_from_file(self):
        """Manually reload the last optimization results JSON file."""
        if not self._vault_name:
            self._cycle_lbl.setText("No vault selected – run optimization first")
            self._cycle_lbl.setStyleSheet("color:#ff6b6b; font-size:10px; background:transparent;")
            return

        results_file = f"{self._vault_name}_optimization_results.json"
        if not os.path.exists(results_file):
            self._cycle_lbl.setText(f"File not found: {results_file}")
            self._cycle_lbl.setStyleSheet("color:#ff6b6b; font-size:10px; background:transparent;")
            return

        try:
            with open(results_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.update_from_results(data)
        except Exception as e:
            self._cycle_lbl.setText(f"Error reading file: {e}")
            self._cycle_lbl.setStyleSheet("color:#ff6b6b; font-size:10px; background:transparent;")
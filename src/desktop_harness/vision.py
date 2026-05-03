"""Vision tier — the missing layer that makes desktop-harness peer-level
to computer-use for sparse-AX (Electron) apps.

Three primitives:
  * `app_class(app)` — classify an app: electron, native_ax, applescript_friendly.
    Electron apps short-circuit straight to the vision tier. No more wasted AX calls.
  * `screenshot_with_grid(app=None)` — annotated PNG with a labeled coordinate
    grid burnt in. The agent reads "click at G7" and we map it to pixels.
  * `smart_click(target, app=None)` — auto-falls-through AX → OCR → vision.
    One call, never has to choose tiers manually. Reports which tier won.
  * `vision_act(task, app=None)` — return everything the model needs to act:
    grid screenshot (base64), text labels found via OCR, AX summary if any.
    The single tool to wrap "I want to do X but can't guess where".

Why this exists:
  Anthropic computer-use beats us on Electron apps because it goes pixel-first
  and we went AX-first. This module restores parity by giving the agent ONE
  primitive that does the right thing per app class, with the screenshot as
  the universal fallback. Native apps still benefit from the AX fast path.
"""
from __future__ import annotations

import base64
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from .apps import frontmost as _frontmost, app_info, pid_of


# --------------------------------------------------------------------------
# App classifier
# --------------------------------------------------------------------------

# Bundle IDs known to be Electron / Catalyst — sparse AX, drive via vision/keyboard.
ELECTRON_APPS = frozenset({
    "md.obsidian",
    "com.tinyspeck.slackmacgap",      # Slack
    "com.hnc.Discord",                 # Discord
    "com.microsoft.VSCode",            # VS Code
    "com.cursor.Cursor",               # Cursor
    "com.figma.Desktop",               # Figma
    "notion.id",                       # Notion
    "com.linear",                      # Linear
    "com.electron.linear",
    "company.thebrowser.Browser",      # Arc
    "com.spotify.client",              # Spotify
    "us.zoom.xos",                     # Zoom
    "com.todesktop.230313mzl4w4u92",   # Cursor (variant)
    "com.todoist.mac.Todoist",
    "com.warp.Warp",                   # Warp
    "com.todesktop",                   # ToDesktop family
    "com.github.GitHubClient",         # GitHub Desktop
    "ai.perplexity.mac",               # Perplexity
    "com.anthropic.claudefordesktop",  # Claude desktop (Electron-ish)
})

# Bundle IDs with deep AppleScript dictionaries — prefer tell() over AX/vision.
APPLESCRIPT_APPS = frozenset({
    "com.apple.mail",
    "com.apple.iCal",                  # Calendar
    "com.apple.AddressBook",           # Contacts
    "com.apple.Notes",
    "com.apple.reminders",
    "com.apple.Music",
    "com.apple.Photos",
    "com.apple.Safari",
    "com.apple.finder",
    "com.apple.Terminal",
    "com.apple.TextEdit",
    "com.microsoft.Word",
    "com.microsoft.Excel",
    "com.microsoft.Powerpoint",
    "com.omnigroup.OmniFocus3",
    "com.omnigroup.OmniGraffle7",
})


_ELECTRON_LC = frozenset(b.lower() for b in ELECTRON_APPS)
_APPLESCRIPT_LC = frozenset(b.lower() for b in APPLESCRIPT_APPS)


def app_class(app_name: str) -> str:
    """Classify an app for tier selection. Returns one of:
       'electron'     — sparse AX, use vision + keyboard
       'applescript'  — has a scripting dictionary, prefer tell()
       'native_ax'    — full AX support (default)
       'unknown'      — app not running, can't classify
    """
    info = app_info(app_name)
    if info is None:
        return "unknown"
    bid = (info.get("bundle_id") or "").lower()
    if bid in _ELECTRON_LC:
        return "electron"
    if any(bid.startswith(prefix) for prefix in (
        "com.todesktop", "com.electron.", "com.tinyspeck.", "com.spotify.",
    )):
        return "electron"
    if bid in _APPLESCRIPT_LC:
        return "applescript"
    return "native_ax"


def is_electron(app_name: str) -> bool:
    return app_class(app_name) == "electron"


# --------------------------------------------------------------------------
# Grid overlay screenshot — the computer-use trick
# --------------------------------------------------------------------------

def screenshot_with_grid(
    app: Optional[str] = None,
    *,
    grid: int = 12,
    path: Optional[str] = None,
    label_size: int = 14,
) -> dict:
    """Capture a screenshot (full screen or app window) with a labeled grid burnt in.

    The grid divides the image into NxN cells labeled like spreadsheet refs
    (A1, B1, ...). The agent says "click at G7" and we resolve to pixels.

    Returns: {path, width, height, grid, cell_w, cell_h, base64,
              cells: {"A1": [x_center, y_center], ...}}
    """
    from .screen import screenshot, screenshot_window
    if app is not None:
        try:
            raw_path = screenshot_window(app)
        except Exception:
            raw_path = screenshot()
    else:
        raw_path = screenshot()

    # Load + draw grid via PIL if available; otherwise CoreImage fallback.
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        img = Image.open(raw_path).convert("RGB")
    except Exception as e:
        # PIL not installed; degrade to plain screenshot + cells dict
        return _grid_no_pil(raw_path, grid)

    w, h = img.size
    cell_w = w / grid
    cell_h = h / grid

    draw = ImageDraw.Draw(img, "RGBA")
    line_color = (255, 0, 64, 140)
    text_bg = (0, 0, 0, 200)
    text_fg = (255, 255, 255, 255)

    # Vertical lines
    for i in range(1, grid):
        x = int(i * cell_w)
        draw.line([(x, 0), (x, h)], fill=line_color, width=1)
    # Horizontal lines
    for j in range(1, grid):
        y = int(j * cell_h)
        draw.line([(0, y), (w, y)], fill=line_color, width=1)

    # Try a small font; fall back to default if it can't load
    font = None
    try:
        for candidate in (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSMono.ttf",
        ):
            if os.path.exists(candidate):
                font = ImageFont.truetype(candidate, label_size)
                break
    except Exception:
        font = None
    if font is None:
        font = ImageFont.load_default()

    cells: dict[str, list[int]] = {}
    for col in range(grid):
        for row in range(grid):
            label = f"{chr(ord('A') + col)}{row + 1}"
            cx = int(col * cell_w + cell_w / 2)
            cy = int(row * cell_h + cell_h / 2)
            cells[label] = [cx, cy]
            # Top-left of each cell gets a label
            tx = int(col * cell_w + 4)
            ty = int(row * cell_h + 2)
            # Background pill for legibility
            try:
                bbox = draw.textbbox((tx, ty), label, font=font)
                draw.rectangle(bbox, fill=text_bg)
            except Exception:
                pass
            draw.text((tx, ty), label, fill=text_fg, font=font)

    if path is None:
        fd, path = tempfile.mkstemp(suffix=".png", prefix="dh-grid-")
        os.close(fd)
    img.save(path, "PNG", optimize=True)

    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    try:
        os.unlink(raw_path)
    except OSError:
        pass

    return {
        "path": path,
        "width": w, "height": h,
        "grid": grid,
        "cell_w": cell_w, "cell_h": cell_h,
        "cells": cells,
        "base64": b64,
        "instruction": (
            f"Image is divided into a {grid}×{grid} grid labeled A1..{chr(ord('A')+grid-1)}{grid}. "
            f"Each cell is {int(cell_w)}×{int(cell_h)} px. "
            f"To click a cell center, call click_at(x, y) with the coords from cells['<LABEL>']. "
            f"For finer targeting within a cell, offset from the cell's top-left."
        ),
    }


def _grid_no_pil(raw_path: str, grid: int) -> dict:
    """PIL absent. Return the raw screenshot + a cells dict computed from
    measured display size (no overlay drawn)."""
    from .screen import main_display_size
    w, h = main_display_size()
    cell_w = w / grid
    cell_h = h / grid
    cells = {}
    for col in range(grid):
        for row in range(grid):
            label = f"{chr(ord('A') + col)}{row + 1}"
            cells[label] = [int(col * cell_w + cell_w / 2), int(row * cell_h + cell_h / 2)]
    return {
        "path": raw_path,
        "width": w, "height": h,
        "grid": grid,
        "cell_w": cell_w, "cell_h": cell_h,
        "cells": cells,
        "base64": None,
        "instruction": "PIL not installed — overlay omitted, cells dict still valid.",
    }


def click_cell(label: str, *, grid: int = 12, app: Optional[str] = None) -> dict:
    """Click the center of a labeled grid cell (e.g. 'G7')."""
    from .input import click_at
    snap = screenshot_with_grid(app=app, grid=grid)
    cell = snap["cells"].get(label.upper())
    if cell is None:
        return {"ok": False, "error": f"unknown cell label: {label}"}
    click_at(cell[0], cell[1])
    return {"ok": True, "cell": label.upper(), "coords": cell}


# --------------------------------------------------------------------------
# smart_click — the auto-tier-falling primitive
# --------------------------------------------------------------------------

def smart_click(
    target: str,
    *,
    app: Optional[str] = None,
    case_insensitive: bool = True,
    timeout: float = 5.0,
) -> dict:
    """Click the best match for `target`. Tries tiers in order, reports which won.

    Tier order:
      1. AX find by exact title (fastest, most reliable for native apps)
      2. AX find by title_contains (handles "Save..." vs "Save")
      3. AX find by description / help / placeholder (catches icon buttons)
      4. OCR full screen (or app window) for the text, click pixel center
      5. Return without clicking — emit a vision_act payload so the agent can
         look at the screenshot and decide visually.

    Skips tiers 1-3 entirely if `app` is in ELECTRON_APPS (saves ~2s per call).
    """
    out: dict = {"target": target, "app": app, "tried": []}

    # Tier classification
    cls = app_class(app) if app else "unknown"
    out["app_class"] = cls

    # Native AX tiers (skip for Electron apps)
    if app and cls != "electron":
        from .ax import find, click_element
        # Tier 1: exact title
        out["tried"].append("ax_title_exact")
        el = find(app, title=target)
        if el is not None and click_element(el):
            out["tier"] = "ax_title_exact"
            out["ok"] = True
            return out
        # Tier 2: title_contains
        out["tried"].append("ax_title_contains")
        el = find(app, title_contains=target)
        if el is not None and click_element(el):
            out["tier"] = "ax_title_contains"
            out["ok"] = True
            return out
        # Tier 3: description / help match
        out["tried"].append("ax_describe_match")
        for filt in (
            {"description": target},
            {"placeholder": target},
        ):
            el = find(app, **filt)
            if el is not None and click_element(el):
                out["tier"] = "ax_describe_match"
                out["ok"] = True
                return out

    # Tier 4: OCR
    out["tried"].append("ocr_screen")
    from .ocr import find_text_on_screen
    pt = find_text_on_screen(target, case_insensitive=case_insensitive)
    if pt is not None:
        from .input import click_at
        click_at(pt[0], pt[1])
        out["tier"] = "ocr_screen"
        out["coords"] = list(pt)
        out["ok"] = True
        return out

    # Tier 5: nothing worked — return a vision payload for the agent
    out["tried"].append("vision_handoff")
    out["tier"] = "vision_handoff"
    out["ok"] = False
    out["vision"] = vision_act(f"click '{target}'", app=app)
    out["hint"] = (
        "Could not find via AX or OCR. Inspect the grid screenshot in 'vision' "
        "and call click_cell(label) or click_at(x, y) directly."
    )
    return out


# --------------------------------------------------------------------------
# vision_act — wrap everything an agent needs to ACT visually
# --------------------------------------------------------------------------

def vision_act(task: str, *, app: Optional[str] = None, grid: int = 12) -> dict:
    """One call → grid screenshot + OCR text + AX summary + suggested next steps.

    Use when the agent doesn't know where the thing is. Avoids the "AX returns
    nothing → agent retries forever" trap by handing back a screenshot the
    agent can reason about visually, with ready-made coords for every cell.
    """
    out: dict = {"task": task, "app": app}
    if app:
        out["app_class"] = app_class(app)
        out["frontmost"] = (_frontmost() or {}).get("name")

    grid_snap = screenshot_with_grid(app=app, grid=grid)
    out["screenshot"] = {
        "path": grid_snap["path"],
        "width": grid_snap["width"],
        "height": grid_snap["height"],
        "grid": grid_snap["grid"],
        "instruction": grid_snap["instruction"],
        "cells_sample": dict(list(grid_snap["cells"].items())[:6]),
        "base64_size": len(grid_snap.get("base64") or ""),
        "base64": grid_snap.get("base64"),
    }

    # Quick OCR pass — text + pixel coords
    from .ocr import ocr
    try:
        results = ocr(grid_snap["path"], fast=True)
        # Convert OCR bbox (normalized, bottom-left origin) → top-left pixel coords
        w, h = grid_snap["width"], grid_snap["height"]
        labeled: list[dict] = []
        for r in results:
            text = r.get("text", "").strip()
            if not text:
                continue
            x, y, bw, bh = r.get("bbox", (0, 0, 0, 0))
            cx = int((x + bw / 2) * w)
            cy = int((1 - (y + bh / 2)) * h)
            labeled.append({"text": text, "x": cx, "y": cy, "confidence": r.get("confidence", 0)})
        out["text_on_screen"] = labeled[:50]
    except Exception as e:
        out["text_on_screen"] = []
        out["ocr_error"] = str(e)

    # AX summary if the app supports it
    if app and out.get("app_class") == "native_ax":
        try:
            from .snapshot import accessibility_snapshot
            snap = accessibility_snapshot(app, max_elements=80, interactive_only=True, include_static_text=False)
            out["ax_summary"] = snap.get("summary", {})
            # First 10 actionable elements (with refs)
            def pick(nodes, found):
                for n in nodes:
                    if n.get("ref") and n.get("role") in ("AXButton", "AXMenuItem", "AXTextField", "AXTextArea"):
                        found.append({k: v for k, v in n.items() if k != "children"})
                    pick(n.get("children", []), found)
                return found
            out["ax_actionable"] = pick(snap.get("tree", []), [])[:10]
        except Exception as e:
            out["ax_error"] = str(e)

    out["recommendations"] = _recommend_next(task, out)
    return out


def _recommend_next(task: str, ctx: dict) -> list[str]:
    """Heuristic next-step suggestions based on what we found."""
    recs = []
    cls = ctx.get("app_class")
    if cls == "electron":
        recs.append("Electron app — try `key('cmd+shift+p')` for the command palette, then type the action name.")
    if cls == "applescript":
        recs.append(f"App has AppleScript dictionary — try tell('{ctx.get('app')}', 'your command') first.")
    text_hits = ctx.get("text_on_screen") or []
    task_lc = task.lower()
    matches = [t for t in text_hits if any(w in t["text"].lower() for w in task_lc.split() if len(w) > 2)]
    if matches:
        first = matches[0]
        recs.append(f"OCR sees relevant text {first['text']!r} at ({first['x']}, {first['y']}). "
                    f"Call click_at({first['x']}, {first['y']}).")
    if ctx.get("ax_actionable"):
        recs.append("AX actionable refs available — call ax_click(ref) on the matching one.")
    if not recs:
        recs.append("Inspect the grid screenshot. Use click_cell('<LABEL>') or click_at(x, y) directly.")
    return recs

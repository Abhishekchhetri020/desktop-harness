"""OCR via the macOS Vision framework. No Tesseract, no network."""
from __future__ import annotations
import os
from typing import Optional

import objc
from Vision import (
    VNRecognizeTextRequest,
    VNImageRequestHandler,
    VNRequestTextRecognitionLevelAccurate,
    VNRequestTextRecognitionLevelFast,
)
from Foundation import NSURL


def ocr(image_path: str, *, fast: bool = False, languages: list[str] | None = None) -> list[dict]:
    """Read text from an image. Returns list of {text, confidence, bbox}.
    bbox is (x, y, w, h) in NORMALIZED coords (0-1, origin bottom-left)."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)

    url = NSURL.fileURLWithPath_(image_path)
    handler = VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(
        VNRequestTextRecognitionLevelFast if fast else VNRequestTextRecognitionLevelAccurate
    )
    request.setUsesLanguageCorrection_(True)
    if languages:
        request.setRecognitionLanguages_(languages)

    err = None
    ok = handler.performRequests_error_([request], err)
    results = request.results() or []
    out = []
    for obs in results:
        cands = obs.topCandidates_(1)
        if not cands:
            continue
        top = cands[0]
        bbox = obs.boundingBox()
        out.append({
            "text": str(top.string()),
            "confidence": float(top.confidence()),
            "bbox": (float(bbox.origin.x), float(bbox.origin.y),
                     float(bbox.size.width), float(bbox.size.height)),
        })
    return out


def ocr_region(x: int, y: int, w: int, h: int, *, fast: bool = False) -> list[dict]:
    """Screenshot a region, then OCR it."""
    from .screen import screenshot_region
    path = screenshot_region(x, y, w, h)
    try:
        return ocr(path, fast=fast)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def ocr_window(app_name: str, *, index: int = 0, fast: bool = False) -> list[dict]:
    """Screenshot a specific app window, then OCR it."""
    from .screen import screenshot_window
    path = screenshot_window(app_name, index=index)
    try:
        return ocr(path, fast=fast)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def find_text_on_screen(needle: str, *, case_insensitive: bool = True,
                        screen_width: int | None = None,
                        screen_height: int | None = None) -> tuple[int, int] | None:
    """Find `needle` on the full screen via OCR; return (x, y) center in pixel coords.
    Useful when an element has no AX representation."""
    from .screen import screenshot, main_display_size
    path = screenshot()
    try:
        results = ocr(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if screen_width is None or screen_height is None:
        screen_width, screen_height = main_display_size()
    cmp_needle = needle.lower() if case_insensitive else needle
    for r in results:
        text = r["text"].lower() if case_insensitive else r["text"]
        if cmp_needle in text:
            x, y, w, h = r["bbox"]
            cx = (x + w / 2) * screen_width
            cy = (1 - (y + h / 2)) * screen_height  # flip — Vision origin is bottom-left
            return (int(cx), int(cy))
    return None

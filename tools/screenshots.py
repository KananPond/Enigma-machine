"""Take the pictures used in the README.

The window is rendered into a bitmap with ``PrintWindow`` and the raw pixels
are written straight out as PNG, so nothing beyond the standard library is
needed to keep ``docs/`` up to date.

    python tools/screenshots.py            # all pictures
    python tools/screenshots.py --only break
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import struct
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def hwnd_of(widget) -> int:
    """Return the top level window handle behind a Tk widget."""
    widget.update_idletasks()
    handle = widget.winfo_id()
    return user32.GetParent(handle) or handle


def capture(handle: int) -> tuple[int, int, bytes]:
    """Render *handle* into a buffer of RGB bytes, top row first."""
    rect = wintypes.RECT()
    user32.GetWindowRect(handle, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise RuntimeError("window has no size")

    window_dc = user32.GetWindowDC(handle)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    user32.PrintWindow(handle, memory_dc, 2)  # PW_RENDERFULLCONTENT

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(handle, window_dc)

    raw = buffer.raw
    rgb = bytearray(width * height * 3)
    rgb[0::3] = raw[2::4]
    rgb[1::3] = raw[1::4]
    rgb[2::3] = raw[0::4]
    return width, height, bytes(rgb)


def save_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    stride = width * 3
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw.extend(rgb[row * stride : (row + 1) * stride])

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


# -------------------------------------------------------------------- scenes
def _pump(app, seconds: float = 0.4) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def _shoot(widget, path: Path) -> None:
    _pump(widget.winfo_toplevel())
    width, height, rgb = capture(hwnd_of(widget))
    save_png(path, width, height, rgb)
    print(f"  {path.name}  {width}x{height}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="message|decode|break|keycard|help|samples")
    options = parser.parse_args()

    from enigma.samples import get as get_sample
    from enigma_gui.app import EnigmaApp

    docs = ROOT / "docs"
    app = EnigmaApp()
    app.geometry("1460x920+30+20")
    app.update()
    _pump(app, 0.5)

    # a machine with cables, so the plugboard has something to show
    app.rebuild(rotors=["II", "IV", "I"], rings="AAA", positions="ADU",
                plugboard="AV BS CG DL FU HZ")
    app.machine.set_positions("ADU")
    app.key = app.key.with_(positions="ADU")
    app.refresh()
    _pump(app, 0.2)

    want = options.only

    if not want or want == "message":
        print("message:")
        app.press("B")
        app.switch_tab("message")
        app.set_direction("encrypt")
        app.msg_input.delete("1.0", "end")
        app.msg_input.insert(
            "1.0",
            "THE CONVOY LEFT THE HARBOUR BEFORE DAWN AND HEADED NORTH WEST. "
            "VISIBILITY IS POOR. REPORT ANY CONTACT AT ONCE.",
        )
        app._update_counter()
        app.run_message()
        _shoot(app, docs / "screen-message.png")

    if not want or want in ("decode", "break"):
        app.set_direction("encrypt")
        if not app.last_output:
            app.msg_input.delete("1.0", "end")
            app.msg_input.insert("1.0", "ATTACK AT DAWN")
            app.run_message()

    if not want or want == "decode":
        print("decode:")
        app.switch_tab("decode")
        app.dec_input.delete("1.0", "end")
        app.dec_input.insert("1.0", app.last_output)
        app.run_decode()
        _pump(app, 0.4)
        _shoot(app, docs / "screen-decode.png")

    if not want or want == "break":
        print("break:")
        sample = get_sample("africa")
        app.switch_tab("break")
        app.brk_input.delete("1.0", "end")
        app.brk_input.insert("1.0", sample.ciphertext)
        app.brk_crib.delete(0, "end")
        app.brk_crib.insert(0, "ATTACK AT FIRST LIGHT")
        app.brk_offset.delete(0, "end")
        app.brk_offset.insert(0, str(sample.crib_offset))
        app.brk_rings.delete(0, "end")
        app.brk_rings.insert(0, sample.key.rings)
        app.run_break()
        deadline = time.time() + 120
        while app.job is not None and time.time() < deadline:
            app.update()
            time.sleep(0.03)
        _pump(app, 0.6)
        _shoot(app, docs / "screen-break.png")

    if not want or want == "keycard":
        print("keycard:")
        app.open_keycard()
        window = app.winfo_children()[-1]
        _pump(app, 0.3)
        _shoot(window, docs / "screen-keycard.png")
        window.destroy()

    if not want or want == "help":
        print("help:")
        app.open_help()
        window = app.winfo_children()[-1]
        _pump(app, 0.3)
        _shoot(window, docs / "screen-help.png")
        window.destroy()

    if not want or want == "samples":
        print("samples:")
        app.open_samples()
        window = app.winfo_children()[-1]
        _pump(app, 0.3)
        _shoot(window, docs / "screen-samples.png")
        window.destroy()

    app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

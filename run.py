"""Entry point of the Enigma machine.

    python run.py
"""

from __future__ import annotations

import sys
import traceback


def _report(error: Exception) -> None:
    """Show a startup failure even when there is no console window."""
    detail = traceback.format_exc()
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("ENIGMA · M3", f"启动失败：{error}\n\n{detail[-900:]}")
        root.destroy()
    except Exception:
        print(detail, file=sys.stderr)


def main() -> int:
    try:
        from enigma_gui import main as run
    except Exception as error:  # pragma: no cover - broken installation
        _report(error)
        return 1
    try:
        return run()
    except Exception as error:  # pragma: no cover - defensive
        _report(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

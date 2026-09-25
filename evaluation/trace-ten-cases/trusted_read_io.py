"""Windows file transport for the checked-in Docs trusted-read bridge."""
import json
import sys
from pathlib import Path

if sys.stdin.isatty():
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-10)
    mode = ctypes.c_ulong()
    ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    ctypes.windll.kernel32.SetConsoleMode(handle, mode.value & ~6)

root = Path(__file__).resolve().parent
print("READY", flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    for item in batch:
        target = Path(item["path"].removeprefix("/" )).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Output outside workbook working directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["text"], encoding="utf-8", newline="")
    print("COMMITTED", flush=True)
    break

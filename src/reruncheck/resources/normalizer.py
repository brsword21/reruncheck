"""Original synthetic normalizer, not third-party fixture code."""

import sys
from pathlib import Path

path = Path("data.txt")
value = path.read_bytes().replace(b"\r\n", b"\n").strip()
if sys.argv[1] == "broken":
    value += b"!"
path.write_bytes(value + b"\n")

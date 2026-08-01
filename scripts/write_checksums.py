from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    target = directory / "SHA256SUMS.txt"
    artifacts = tuple(
        path
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path != target
    )
    lines = []
    for path in artifacts:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(directory).as_posix()}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

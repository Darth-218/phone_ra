from pathlib import Path
from typing import List


def load_sites_file(path: Path) -> List[str]:
    """Load retailer links from a text file.

    One link per line. Blank lines and lines starting with ``#`` are ignored,
    and trailing ``#`` comments are stripped. Duplicate links are removed
    while preserving order.
    """
    if not path.exists():
        raise FileNotFoundError(f"Sites file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Sites file is not a regular file: {path}")

    sites: List[str] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not line.startswith(("http://", "https://")):
            raise ValueError(
                f"{path}:{lineno}: expected an http(s) retailer link, got {line!r}"
            )
        sites.append(line)

    unique: List[str] = []
    seen = set()
    for site in sites:
        if site not in seen:
            seen.add(site)
            unique.append(site)

    if not unique:
        raise ValueError(f"{path}: no retailer links found")

    return unique

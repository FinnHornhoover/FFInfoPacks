import sys
import json
from pathlib import Path

from tqdm import tqdm


def extract_derived_info(in_dir: Path, out_info_dir: Path):
    with open(in_dir / "areas.json", "r") as f:
        areas = json.load(f)

    with open(in_dir / "xdt.json", "r") as f:
        xdt = json.load(f)

    out_info_dir.mkdir(parents=True, exist_ok=True)

    # TODO: Implement this script


def main(in_root: Path, in_released_root: Path):
    in_dirs = [p for p in in_root.iterdir() if p.is_dir()]
    for in_dir in tqdm(in_dirs):
        extract_derived_info(in_dir, in_dir / "info")
        extract_derived_info(in_released_root / in_dir.name, in_dir / "info_released")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_derived_info.py <in_root> <in_released_root>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]))

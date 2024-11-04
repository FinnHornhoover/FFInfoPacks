import sys
import json
from pathlib import Path

from tqdm import tqdm


def extract_derived_info(out_dir: Path):
    with open(out_dir / "areas.json", "r") as f:
        areas = json.load(f)

    with open(out_dir / "xdt.json", "r") as f:
        xdt = json.load(f)

    # TODO: Implement this script


def main(out_root: Path):
    out_dirs = [p for p in out_root.iterdir() if p.is_dir()]
    for out_dir in tqdm(out_dirs):
        extract_derived_info(out_dir)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_derived_info.py <out_root>")
        sys.exit(1)

    main(Path(sys.argv[1]))

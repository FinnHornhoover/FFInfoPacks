import os
import sys
import json
from pathlib import Path

from tqdm import tqdm


def extract_derived_info(out_dir: Path, out_info_dir: Path):
    with open(out_dir / "areas.json", "r") as f:
        areas = json.load(f)

    with open(out_dir / "xdt.json", "r") as f:
        xdt = json.load(f)

    os.makedirs(out_info_dir, exist_ok=True)

    # TODO: Implement this script


def main(in_root: Path, out_info_dir: Path):
    out_dirs = [p for p in in_root.iterdir() if p.is_dir()]
    for out_dir in tqdm(out_dirs):
        extract_derived_info(out_dir, out_info_dir)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_derived_info.py <in_root> <out_info_dir>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]))

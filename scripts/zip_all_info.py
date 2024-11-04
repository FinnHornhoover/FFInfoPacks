import sys
import shutil
from pathlib import Path

import yaml
from tqdm import tqdm


def main(config_path: Path, in_root: Path, out_root: Path):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["config"]

    out_root.mkdir(parents=True, exist_ok=True)

    in_dirs = [p for p in in_root.iterdir() if p.is_dir()]
    for in_dir in tqdm(in_dirs):
        build = in_dir.name
        build_config = config[build]
        nickname = build_config.get("nickname", "unnamed")
        revision = build_config["revision"]

        out_path = out_root / f"{nickname}_{build}_r{revision}"

        shutil.make_archive(out_path, "zip", in_dir)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python zip_all_info.py <config_path> <in_root> <out_root>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))

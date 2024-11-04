import sys
import json
import traceback
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import ImageOps
from tqdm import tqdm

import unitypack


def fixext(name: str) -> str:
    tab = {"dds": "png", "nif": "obj", "kfm": "obj", "wav": "ogg",
           "mp3": "ogg", "jpg": "png", "psd": "png", "dds.asset": "png",
           "tga": "png", "tif": "png", "dds.mat": "png", "asset": "png"}

    for ext in tab.keys():
        if name.endswith(ext):
            outname = name[:-len(ext)]
            outname += tab[ext]
            return outname

    return name


def handle_texture(d: Any, outpath: str):
    try:
        image = d.image
    except NotImplementedError:
        print("WARNING: Texture format not implemented. Skipping %r." % (outpath))
        return

    if image is None:
        print("WARNING: %s is an empty image" % (outpath))
        return

    # Texture2D objects are flipped
    img = ImageOps.flip(image)
    # PIL has no method to write to a string :/
    output = BytesIO()
    img.save(output, format="png")
    with open(outpath, "wb") as f:
        f.write(output.getvalue())


def icon_bundle_extract(path: Path, outdir: Path):
    try:
        with open(path / "Icons.resourceFile", "rb") as f:
            asset = unitypack.load(f).assets[0]

        tutasset = None
        if (path / "Tutorial.resourceFile").is_file():
            with open(path / "Tutorial.resourceFile", "rb") as f:
                tutasset = unitypack.load(f).assets[0]

        trainasset = None
        if (path / "TrainingGrounds.resourceFile").is_file():
            with open(path / "TrainingGrounds.resourceFile", "rb") as f:
                trainasset = unitypack.load(f).assets[0]

        cont = asset.objects[1].read()["m_Container"]
        for path, mtdt in cont:
            path_obj = Path(path)
            (outdir / path_obj.parent).mkdir(parents=True, exist_ok=True)

            outname = fixext(path_obj.name)
            outpath = outdir / path_obj.parent / outname

            if outpath.exists():
                print("** {} exists, skipping...".format(outpath))
                continue

            obj_ptr = mtdt["asset"]
            try:
                obj = obj_ptr.object
            except:
                if tutasset is None:
                    if trainasset is None:
                        print("unresolved asset reference: {} {}".format(obj_ptr.source_asset.asset_refs, outpath))
                        traceback.print_exc(file=sys.stdout)
                        continue
                    obj = trainasset.objects[obj_ptr.path_id]
                else:
                    obj = tutasset.objects[obj_ptr.path_id]

            try:
                handle_texture(obj.read(), outpath)
            except:
                print("** error while handling object {} {}".format(mtdt["asset"], outpath))
                traceback.print_exc(file=sys.stdout)

    except:
        print("* error while handling assetbundle Icons.resourceFile {}".format(outdir))
        traceback.print_exc(file=sys.stdout)


def xdt_bundle_extract(path: Path, outdir: Path):
    with open(path / "TableData.resourceFile", "rb") as f:
        tabledata = unitypack.load(f).assets[0]

    xdtdata, areadata = None, None
    for obj in tabledata.objects.values():
        if obj.type == "XdtTableScript":
            xdtdata = obj.read()
        elif obj.type == "WorldNameScript":
            areadata = obj.read()

        if None not in (xdtdata, areadata):
            break

    if xdtdata:
        out = {}
        for tname, table in xdtdata.items():
            out[tname] = {}
            try:
                for dname, data in table.items():
                    out[tname][dname] = data
            except:
                out[tname] = "<err>"

        with open(outdir / "xdt.json", "w") as f:
            json.dump(out, f, indent=4)

    if areadata:
        areas = [
            obj
            for obj in areadata["m_pWorldNameData"]
            if obj["Area"]["width"] * obj["Area"]["height"] > 0 and obj["DongName"] != "unknown"
        ]

        with open(outdir / "areas.json", "w") as f:
            json.dump(areas, f, indent=4)


def main(asset_root: Path, output_root: Path):
    asset_paths = [p for p in asset_root.iterdir() if p.is_dir()]
    for asset_path in tqdm(asset_paths):
        output_path = output_root / asset_path.name
        output_path.mkdir(parents=True, exist_ok=True)

        icon_bundle_extract(asset_path, output_path)
        xdt_bundle_extract(asset_path, output_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_game_info.py <asset_root> <output_root>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]))

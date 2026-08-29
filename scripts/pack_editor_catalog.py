import base64
import gzip
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"FFIPED01"
PBKDF2_ITERATIONS = 600_000
TYPE_TO_CATEGORY = {
    "Weapon": "weaponitem",
    "Body": "shirtsitem",
    "Legs": "pantsitem",
    "Shoes": "shoesitem",
    "Hat": "hatitem",
    "Glasses": "glassitem",
    "Backpack": "backitem",
    "General": "generalitem",
    "CRATE": "chestitem",
    "Vehicle": "vehicleitem",
}


def revision_from_name(path: Path) -> int:
    match = re.search(r"_r(\d+)", path.name)
    if match is None:
        raise ValueError(f"Could not determine Retrobution revision from {path.name}")
    return int(match.group(1))


def build_payload(archive: zipfile.ZipFile, revision: int) -> bytes:
    item_info = json.loads(archive.read("info/item_info.json"))
    items = []
    icon_paths = set()

    for source in item_info.values():
        item_type = source["Type"]
        category = TYPE_TO_CATEGORY.get(item_type)
        if category is None:
            continue

        icon_path = source["Icon"]
        icon_paths.add(icon_path)
        items.append(
            {
                "id": int(source["ItemID"]),
                "category": category,
                "name": source["Name"],
                "description": source["Description"],
                "type": item_type,
                "weaponType": source["WeaponType"] if item_type == "Weapon" else None,
                "level": int(source["ContentLevel"]),
                "rarity": source["Rarity"],
                "gender": source["Gender"],
                "tradeable": bool(source["Tradeable"]),
                "sellable": bool(source["Sellable"]),
                "icon": icon_path,
            }
        )

    items.sort(key=lambda item: (item["category"], item["id"]))
    icons = {}
    for icon_path in sorted(icon_paths):
        safe_path = PurePosixPath(icon_path)
        if safe_path.is_absolute() or ".." in safe_path.parts:
            raise ValueError(f"Unsafe icon path: {icon_path}")
        try:
            icons[icon_path] = base64.b64encode(archive.read(icon_path)).decode("ascii")
        except KeyError as error:
            raise ValueError(f"Referenced icon is missing from artifact: {icon_path}") from error

    payload = {
        "formatVersion": 1,
        "revision": revision,
        "items": items,
        "icons": icons,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(serialized, compresslevel=9, mtime=0)


def encrypt_payload(compressed: bytes, passphrase: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=32,
    )
    ciphertext = AESGCM(key).encrypt(nonce, compressed, MAGIC)
    return MAGIC + salt + nonce + ciphertext


def main(input_zip: Path, output_file: Path) -> None:
    passphrase = os.environ.get("EDITOR_KEY")
    if passphrase is None or len(passphrase) < 12:
        raise ValueError("EDITOR_KEY must be set and contain at least 12 characters")

    with zipfile.ZipFile(input_zip) as archive:
        compressed = build_payload(archive, revision_from_name(input_zip))

    encrypted = encrypt_payload(compressed, passphrase)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(encrypted)
    print(f"Wrote {len(encrypted):,} encrypted bytes to {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python pack_editor_catalog.py <unfiltered_retrobution.zip> <catalog.enc>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]))

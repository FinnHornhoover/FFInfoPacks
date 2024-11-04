import sys
import asyncio
from pathlib import Path
from typing import Any

import aiofiles
import httpx
import yaml
from tqdm.asyncio import tqdm_asyncio

REPO_RELEASE_URL = "https://github.com/FinnHornhoover/FFInfoPacks/releases/latest/download"


async def download_file(client: httpx.AsyncClient, url: str, path: Path):
    async with client.stream("GET", url) as stream:
        stream.raise_for_status()

        async with aiofiles.open(path, "wb") as f:
            async for chunk in stream.aiter_bytes(chunk_size=(1 << 16)):
                await f.write(chunk)


async def download_zip_or_resources(
    client: httpx.AsyncClient,
    build: str,
    build_config: dict[str, Any],
    asset_root: Path,
    artifact_root: Path,
):
    base_url = build_config["url"]
    nickname = f"_{build_config['nickname']}" if "nickname" in build_config else ""
    revision = build_config["revision"]
    zip_name = f"{build}_r{revision}{nickname}.zip"

    try:
        await download_file(
            client,
            f"{REPO_RELEASE_URL}/{zip_name}",
            artifact_root / zip_name,
        )
    except httpx.HTTPStatusError:
        await asyncio.gather(
            *[
                download_file(
                    client,
                    f"{base_url}/{resource}",
                    asset_root / build / resource,
                )
                for resource in build_config["resources"]
            ]
        )


async def download_resources(
    config: dict[str, dict[str, Any]], asset_root: Path, artifact_root: Path
):
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=5),
        timeout=httpx.Timeout(None),
    ) as client:
        coroutines = []

        artifact_root.mkdir(parents=True, exist_ok=True)

        for build, build_config in config.items():
            (asset_root / build).mkdir(parents=True, exist_ok=True)

            coroutines.append(
                download_zip_or_resources(
                    client, build, build_config, asset_root, artifact_root
                )
            )

        await tqdm_asyncio.gather(*coroutines)


async def main(config_path: str, asset_root: str, artifact_root: str):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["config"]
    await download_resources(config, Path(asset_root), Path(artifact_root))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python download_resources.py <config_path> <asset_root> <artifact_root>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))

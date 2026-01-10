import sys
import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
import httpx
import yaml
from tqdm.asyncio import tqdm_asyncio

REPO_RELEASE_URL = "https://github.com/FinnHornhoover/FFInfoPacks/releases/latest/download"


def pull_table_data(server_data_root: Path, server_data_config: dict[str, Any]):
    repo_name_path = Path(server_data_config["repository"].strip("/"))
    clone_path = server_data_root / repo_name_path.parent
    clone_path.mkdir(parents=True, exist_ok=True)

    url = f"ssh://git@github.com/{repo_name_path}.git"
    repo_path = clone_path / repo_name_path.name

    if not repo_path.is_dir():
        subprocess.run(["git", "clone", "-q", url, repo_path])


async def get_json_info(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    response = await client.get(url)
    response.raise_for_status()

    return response.json()


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
    must_fetch_zip: bool,
):
    if "api-url" in build_config:
        api_info = await get_json_info(client, build_config["api-url"])
        game_version = api_info["game_versions"][0]
        version_url = f"{build_config['api-url']}/versions/{game_version}.json"
        version_info = await get_json_info(client, version_url)

        base_url = version_info["asset_url"]
    else:
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
        if must_fetch_zip:
            raise

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
    config: dict[str, dict[str, Any]], asset_root: Path, artifact_root: Path, server_data_root: Optional[Path]
):
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=5),
        timeout=httpx.Timeout(None),
        follow_redirects=True,
    ) as client:
        coroutines = []

        artifact_root.mkdir(parents=True, exist_ok=True)

        for build, build_config in config.items():
            (asset_root / build).mkdir(parents=True, exist_ok=True)

            if server_data_root:
                pull_table_data(server_data_root, build_config["server-data"])

            coroutines.append(
                download_zip_or_resources(
                    client, build, build_config, asset_root, artifact_root, must_fetch_zip=(server_data_root is None)
                )
            )

        await tqdm_asyncio.gather(*coroutines)


async def main(config_path: Path, asset_root: Path, artifact_root: Path, server_data_root: Optional[Path] = None):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["config"]

    await download_resources(config, asset_root, artifact_root, server_data_root)

    for build in asset_root.iterdir():
        if not any(build.iterdir()):
            build.rmdir()


if __name__ == "__main__":
    if len(sys.argv) != 4 and len(sys.argv) != 5:
        print("Usage: python download_resources.py <config_path> <asset_root> <artifact_root> [<server_data_root>]")
        sys.exit(1)

    asyncio.run(main(*map(Path, sys.argv[1:])))

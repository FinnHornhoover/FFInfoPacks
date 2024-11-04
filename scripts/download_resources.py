import sys
import asyncio
from pathlib import Path
from typing import Any

import aiofiles
import httpx
import yaml
from tqdm.asyncio import tqdm_asyncio


async def download_file(client: httpx.AsyncClient, url: str, path: Path):
    async with client.stream("GET", url) as stream:
        async with aiofiles.open(path, "wb") as f:
            async for chunk in stream.aiter_bytes(chunk_size=(1 << 16)):
                await f.write(chunk)


async def download_resources(config: dict[str, dict[str, Any]]):
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=5),
        timeout=httpx.Timeout(None),
    ) as client:
        coroutines = []

        for build, build_config in config.items():
            base_url = build_config["url"]
            base_path = Path("assets") / build
            base_path.mkdir(parents=True, exist_ok=True)

            for resource in build_config["resources"]:
                coroutines.append(
                    download_file(
                        client,
                        f"{base_url}/{resource}",
                        base_path / resource,
                    )
                )

        await tqdm_asyncio.gather(*coroutines)


async def main(config_path: str):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["config"]
    await download_resources(config)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python download_resources.py <config_path>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))

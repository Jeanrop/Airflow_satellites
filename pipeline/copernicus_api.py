import asyncio
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
import rasterio
from dotenv import load_dotenv
from rasterio.merge import merge

logger = logging.getLogger(__name__)

load_dotenv()

USERNAME = os.getenv("COPERNICUS_USERNAME")
PASSWORD = os.getenv("COPERNICUS_PASSWORD")

AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"
IMAGE_URL = "https://sh.dataspace.copernicus.eu/process/v1"


@dataclass
class RawScene:
    scene_id: str
    acquisition_datetime: str
    acquisition_date: str
    cloud_cover: float | None
    raw_path: str  # GeoTIFF, band 1 = B04 (red), band 2 = B08 (NIR)


async def get_copernicus_token(client: httpx.AsyncClient) -> str | None:
    """Step 1: get the Copernicus access token."""
    data = {
        "client_id": "cdse-public",
        "username": USERNAME,
        "password": PASSWORD,
        "grant_type": "password",
    }
    response = await client.post(url=AUTH_URL, data=data, timeout=10.0)
    if response.status_code == 200:
        logger.info("Authentication granted ! Retrieved token.")
        return response.json().get("access_token")
    logger.error("Authentication failed : %s %s", response.status_code, response.text)
    return None


async def search_stac_scenes(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    datetime_range: str,
    collections: tuple[str, ...] = ("sentinel-2-l2a",),
    limit: int = 50,
    max_cloud_cover: float = 30.0
) -> dict | None:
    """Step 2: query the STAC catalogue for scene metadata and ids."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "collections": list(collections),
        "bbox": bbox,
        "datetime": datetime_range,
        "limit": limit,
        "query": {"eo:cloud_cover": {"lt": max_cloud_cover}}
    }
    response = await client.post(STAC_URL, json=payload, headers=headers, timeout=15.0)
    if response.status_code != 200:
        logger.error(f"Fail to retrieve data. HTTP : {response.status_code} Error response : {response.text}")
        return None
    return response.json()


def bbox_to_size(bbox: list[float], resolution_m: float = 10.0) -> tuple[int, int]:
    """Return (width, height) in pixels for a bbox at the given resolution."""
    lon_min, lat_min, lon_max, lat_max = bbox
    lat_mid = (lat_min + lat_max) / 2
    width_m = (lon_max - lon_min) * 111_320 * math.cos(math.radians(lat_mid))
    height_m = (lat_max - lat_min) * 110_540
    return round(width_m / resolution_m), round(height_m / resolution_m)


def split_bbox(
    bbox: list[float],
    resolution_m: float = 10.0,
    n: int = 2
) -> list[tuple[list[float], tuple[int, int]]]:
    """Split a bbox into n x n blocks aligned on the pixel grid of the full bbox."""
    lon_min, lat_min, lon_max, lat_max = bbox
    width, height = bbox_to_size(bbox, resolution_m)
    lon_step = (lon_max - lon_min) / width
    lat_step = (lat_max - lat_min) / height

    xs = [round(i * width / n) for i in range(n + 1)]
    ys = [round(j * height / n) for j in range(n + 1)]

    blocks = []
    for j in range(n):
        for i in range(n):
            sub_bbox = [
                lon_min + xs[i] * lon_step,
                lat_min + ys[j] * lat_step,
                lon_min + xs[i + 1] * lon_step,
                lat_min + ys[j + 1] * lat_step,
            ]
            blocks.append((sub_bbox, (xs[i + 1] - xs[i], ys[j + 1] - ys[j])))
    return blocks


def merge_tiles(tile_paths: list[str], output_filename: str) -> None:
    """Merge georeferenced GeoTIFF blocks into a single compressed GeoTIFF."""
    sources = [rasterio.open(p) for p in tile_paths]
    try:
        mosaic, transform = merge(sources)
        profile = sources[0].profile
    finally:
        for src in sources:
            src.close()

    for key in ("blockxsize", "blockysize", "tiled"):
        profile.pop(key, None)
    profile.update(
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=transform,
        compress="deflate",
        predictor=3,
    )
    os.makedirs(os.path.dirname(output_filename) or ".", exist_ok=True)
    with rasterio.open(output_filename, "w", **profile) as dst:
        dst.write(mosaic)

def is_valid_tile(path: str, bbox: list[float], size: tuple[int, int]) -> bool:
    """Check that an existing block matches the expected size and extent."""
    try:
        with rasterio.open(path) as src:
            if (src.width, src.height) != size or src.count != 2:
                return False
            return all(abs(a - b) < 1e-5 for a, b in zip(src.bounds, bbox))
    except rasterio.errors.RasterioIOError:
        return False

async def download_raw_bands(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    acquisition_datetime: str,
    output_filename: str,
    resolution_m: float = 10.0,
    size: tuple[int, int] | None = None
) -> bool:
    """Step 3: download raw B04 and B08 reflectance as a 2-band float32 GeoTIFF."""
    t = datetime.fromisoformat(acquisition_datetime.replace("Z", "+00:00"))
    time_from = (t - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_to = (t + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    width, height = bbox_to_size(bbox, resolution_m)
    if width * height <= 1_000_000:   # about 1000 x 1000 px
        n = 1

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff"
    }
    payload = {
        "input": {
            "bounds": {"bbox": bbox},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": time_from, "to": time_to},
                    "mosaickingOrder": "leastCC"
                }
            }]
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
        },
        "evalscript": """
        //VERSION=3
        function setup() {
          return {
            input: ["B04", "B08"],
            output: { bands: 2, sampleType: "FLOAT32" }
          };
        }
        function evaluatePixel(sample) {
          return [sample.B04, sample.B08];
        }
        """
    }

    logger.info(f"Envoi de la requête B04/B08 ({width}x{height}) pour {acquisition_datetime}...")
    timeout = httpx.Timeout(300.0, connect=10.0)
    max_attempts = 5
    response = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.post(IMAGE_URL, json=payload, headers=headers, timeout=timeout)
        except httpx.TimeoutException:
            logger.warning("Timeout (attempt %d/%d)", attempt, max_attempts)
            response = None
        else:
            if response.status_code < 500:
                break
            logger.warning("Server error %s (attempt %d/%d)", response.status_code, attempt, max_attempts)
        if attempt < max_attempts:
            await asyncio.sleep(5 * attempt)

    if response is None:
        logger.error("Aucune réponse du serveur après %d tentatives.", max_attempts)
        return False
    if response.status_code != 200:
        logger.error("Erreur %s: %s", response.status_code, response.text[:300])
        return False

    os.makedirs(os.path.dirname(output_filename) or ".", exist_ok=True)
    with open(output_filename, "wb") as f:
        f.write(response.content)
    logger.info(f"Succès ! Bandes brutes enregistrées : {output_filename}")
    return True


async def download_raw_bands_tiled(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    acquisition_datetime: str,
    output_filename: str,
    resolution_m: float = 10.0,
    n: int = 2
) -> bool:
    """Download raw bands in n x n sequential API calls, then merge the blocks."""
    width, height = bbox_to_size(bbox, resolution_m)
    if width * height <= 1_000_000:   # about 1000 x 1000 px
        n = 1
    if n == 1:
        return await download_raw_bands(
            client, token, bbox, acquisition_datetime, output_filename, resolution_m
        )
    tile_paths: list[str] = []
    for k, (sub_bbox, size) in enumerate(split_bbox(bbox, resolution_m, n)):
        tile_path = f"{output_filename}.part{k}.tif"
        tile_paths.append(tile_path)

        if os.path.exists(tile_path) and is_valid_tile(tile_path, sub_bbox, size):
            logger.info(f"Bloc {k + 1}/{n * n} déjà présent, ignoré.")
            continue

        logger.info(f"Bloc {k + 1}/{n * n}")
        success = await download_raw_bands(
            client=client,
            token=token,
            bbox=sub_bbox,
            acquisition_datetime=acquisition_datetime,
            output_filename=tile_path,
            resolution_m=resolution_m,
            size=size
        )
        if not success:
            logger.error(f"Échec du bloc {k + 1}/{n * n}, blocs déjà téléchargés conservés pour la reprise.")
            return False

    merge_tiles(tile_paths, output_filename)
    for path in tile_paths:
        os.remove(path)
    logger.info(f"Blocs fusionnés : {output_filename}")
    return True


async def orchestrate_sentinel_pipeline(
    bbox: list[float],
    datetime_range: str,
    output_dir: str = "../data/raw",
    tiles_per_side: int = 2
) -> RawScene | None:
    """Run token, STAC search and raw download. Return the scene or None."""
    async with httpx.AsyncClient() as client:
        # 1. Token
        token = await get_copernicus_token(client)
        if not token:
            logger.error("Arrêt : Impossible de récupérer le token.")
            return None

        # 2. STAC search
        stac_results = await search_stac_scenes(client, token, bbox, datetime_range)
        if not stac_results or "features" not in stac_results:
            logger.error("Échec de la recherche STAC.")
            return None

        features = stac_results.get("features", [])
        logger.info(f"Succès ! {len(features)} produits trouvés.")

        if not features:
            logger.error("Aucune scène disponible pour cette emprise et cette période.")
            return None

        # 3. Least cloudy scene, then raw download in blocks
        feature = min(features, key=lambda f: f["properties"].get("eo:cloud_cover", 100))
        scene_id = feature["id"]
        acquisition_datetime = feature["properties"]["datetime"]
        acquisition_date = acquisition_datetime[:10]
        logger.info(f"ID de la scène sélectionnée : {scene_id}")

        raw_path = os.path.join(output_dir, f"{acquisition_date}_{scene_id}_B04B08.tif")
        success = await download_raw_bands_tiled(
            client=client,
            token=token,
            bbox=bbox,
            acquisition_datetime=acquisition_datetime,
            output_filename=raw_path,
            n=tiles_per_side
        )
        if not success:
            return None

        return RawScene(
            scene_id=scene_id,
            acquisition_datetime=acquisition_datetime,
            acquisition_date=acquisition_date,
            cloud_cover=feature["properties"].get("eo:cloud_cover"),
            raw_path=raw_path
        )
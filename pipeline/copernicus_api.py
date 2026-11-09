import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

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
        print("Authentication granted ! Retrieved token.")
        return response.json().get("access_token")
    print("Authentication failed :", response.status_code, response.text)
    return None


async def search_stac_scenes(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    datetime: str,
    collections=["sentinel-2-l2a"],
    limit=10
) -> dict | None:
    """Step 2: query the STAC catalogue for scene metadata and ids."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "collections": collections,
        "bbox": bbox,
        "datetime": datetime,
        "limit": limit
    }
    response = await client.post(STAC_URL, json=payload, headers=headers, timeout=15.0)
    if response.status_code != 200:
        print(f"Fail to retrieve data. HTTP : {response.status_code} Error response : {response.text}")
        return None
    return response.json()


def bbox_to_size(bbox: list[float], resolution_m: float = 10.0) -> tuple[int, int]:
    """Return (width, height) in pixels for a bbox at the given resolution."""
    lon_min, lat_min, lon_max, lat_max = bbox
    lat_mid = (lat_min + lat_max) / 2
    width_m = (lon_max - lon_min) * 111_320 * math.cos(math.radians(lat_mid))
    height_m = (lat_max - lat_min) * 110_540
    return round(width_m / resolution_m), round(height_m / resolution_m)


async def download_raw_bands(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    acquisition_datetime: str,
    output_filename: str,
    resolution_m: float = 10.0
) -> bool:
    """Step 3: download raw B04 and B08 reflectance as a 2-band float32 GeoTIFF."""
    t = datetime.fromisoformat(acquisition_datetime.replace("Z", "+00:00"))
    time_from = (t - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_to = (t + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    width, height = bbox_to_size(bbox, resolution_m)

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

    print(f"Envoi de la requête B04/B08 ({width}x{height}) pour {acquisition_datetime}...")
    response = await client.post(IMAGE_URL, json=payload, headers=headers, timeout=60.0)

    if response.status_code != 200:
        print(f"Erreur {response.status_code}: {response.text}")
        return False

    os.makedirs(os.path.dirname(output_filename) or ".", exist_ok=True)
    with open(output_filename, "wb") as f:
        f.write(response.content)
    print(f"Succès ! Bandes brutes enregistrées : {output_filename}")
    return True


async def orchestrate_sentinel_pipeline(
    bbox: list[float],
    datetime_range: str,
    output_dir: str = "../data/raw"
) -> RawScene | None:
    """Run token, STAC search and raw download. Return the scene or None."""
    async with httpx.AsyncClient() as client:
        # 1. Token
        token = await get_copernicus_token(client)
        if not token:
            print("Arrêt : Impossible de récupérer le token.")
            return None

        # 2. STAC search
        stac_results = await search_stac_scenes(client, token, bbox, datetime_range)
        if not stac_results or "features" not in stac_results:
            print("Échec de la recherche STAC.")
            return None

        features = stac_results.get("features", [])
        print(f"Succès ! {len(features)} produits trouvés.")

        if not features:
            print("Aucune scène disponible pour cette emprise et cette période.")
            return None

        # 3. Least cloudy scene, then raw download
        feature = min(features, key=lambda f: f["properties"].get("eo:cloud_cover", 100))
        scene_id = feature["id"]
        acquisition_datetime = feature["properties"]["datetime"]
        acquisition_date = acquisition_datetime[:10]
        print(f"ID de la scène sélectionnée : {scene_id}")

        raw_path = os.path.join(output_dir, f"{acquisition_date}_{scene_id}_B04B08.tif")
        success = await download_raw_bands(
            client=client,
            token=token,
            bbox=bbox,
            acquisition_datetime=acquisition_datetime,
            output_filename=raw_path
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
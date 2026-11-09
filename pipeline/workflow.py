"""
This pipeline is used to monitor the NDVI of the Fontainebleau Forest in France.

Information to know:
- Bounding Box format: [lon_min, lat_min, lon_max, lat_max]
- B04: Red band (10m resolution)
- B08: Near-Infrared / NIR band (10m resolution)
- NDVI formula: (B08 - B04) / (B08 + B04)
"""
import asyncio
import os

from copernicus_api import orchestrate_sentinel_pipeline
from db import insert_run
from processing import compute_ndvi

async def main() -> None:
    # Geometrical parameters (ex: Forêt de Fontainebleau)
    bbox = [2.55, 48.33, 2.78, 48.48]
    datetime_range = "2026-05-01T00:00:00Z/2026-06-01T23:59:59Z"

    print("Démarrage du pipeline principal...")

    # Raw B04 / B08 download
    scene = await orchestrate_sentinel_pipeline(
        bbox=bbox,
        datetime_range=datetime_range
    )
    if scene is None:
        print("Le pipeline a rencontré une erreur.")
        return

    # NDVI processing
    ndvi_path = os.path.join("../data", "ndvi", f"{scene.acquisition_date}_{scene.scene_id}_ndvi.tif")
    stats = compute_ndvi(scene.raw_path, ndvi_path)

    # Database insertion
    insert_run(scene, ndvi_path, stats, bbox)

    print("Pipeline exécuté avec succès de bout en bout !")

if __name__ == "__main__":
    asyncio.run(main())
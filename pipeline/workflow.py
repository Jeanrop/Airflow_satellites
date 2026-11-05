"""
This pipeline is used to monitor the NDVI of the Fontainebleau Forest in France.

Information to know:
- Bounding Box format: [lon_min, lat_min, lon_max, lat_max]
- B04: Red band (10m resolution)
- B08: Near-Infrared / NIR band (10m resolution)
- NDVI formula: (B08 - B04) / (B08 + B04)
"""
import asyncio
from copernicus_api import orchestrate_sentinel_pipeline

async def main() -> None:
    # Emprise géographique (ex: Forêt de Fontainebleau)
    bbox = [2.55, 48.33, 2.78, 48.48]
    datetime_range = "2026-05-01T00:00:00Z/2026-06-01T23:59:59Z"

    print("Démarrage du pipeline principal...")

    # Appel unique de la fonction d'orchestration
    success = await orchestrate_sentinel_pipeline(
        bbox=bbox,
        datetime_range=datetime_range,
        output_filename="fontainebleau_output.tiff"
    )

    if success:
        print("Pipeline exécuté avec succès de bout en bout !")
    else:
        print("Le pipeline a rencontré une erreur.")

if __name__ == "__main__":
    asyncio.run(main())
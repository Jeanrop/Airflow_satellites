"""
This pipeline is used to monitor the NDVI of the Fontainebleau Forest in France.

Information to know:
- Bounding Box format: [lon_min, lat_min, lon_max, lat_max]
- B04: Red band (10m resolution)
- B08: Near-Infrared / NIR band (10m resolution)
- NDVI formula: (B08 - B04) / (B08 + B04)
"""

import asyncio
from copernicus_api import call_copernicus_data


async def main() -> None:
    """Main asynchronous entry point for the Fontainebleau NDVI monitoring pipeline."""
    # Bounding box coordinates for the Fontainebleau Forest region
    bbox = [2.55, 48.33, 2.78, 48.48]

    datetime_range = "2026-05-01T00:00:00Z/2026-06-01T23:59:59Z"

    print("Starting Copernicus Sentinel data retrieval...")

    # Await the asynchronous API call
    copernicus_data = await call_copernicus_data(
        bbox=bbox, 
        datetime=datetime_range
    )

    if copernicus_data:
        features = copernicus_data.get("features", [])
        print(f"Success! Retrieved {len(features)} products.")
        
        # Next steps in your pipeline (e.g., extracting asset URLs for B04 and B08)
        for item in features:
            print(f"- Product ID: {item['id']} | Date: {item['properties']['datetime']}")
    else:
        print("No data returned or retrieval failed.")


if __name__ == "__main__":
    asyncio.run(main())
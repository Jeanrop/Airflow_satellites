import os

import psycopg
from dotenv import load_dotenv

from copernicus_api import RawScene

load_dotenv()


def insert_run(scene: RawScene, ndvi_path: str, stats: dict, bbox: list[float]) -> None:
    """Insert one run row (skipped if the scene already exists)."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            """
            INSERT INTO ndvi_runs
              (acquisition_date, scene_id, cloud_cover, ndvi_path,
               ndvi_mean, ndvi_min, ndvi_max, ndvi_std, valid_pixel_pct, geom)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s,
               ST_MakeEnvelope(%s, %s, %s, %s, 4326))
            ON CONFLICT (scene_id) DO NOTHING
            """,
            (
                scene.acquisition_date, scene.scene_id, scene.cloud_cover, ndvi_path,
                stats["ndvi_mean"], stats["ndvi_min"], stats["ndvi_max"],
                stats["ndvi_std"], stats["valid_pixel_pct"], *bbox,
            ),
        )
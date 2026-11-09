import os

import numpy as np
import rasterio


def compute_ndvi(raw_path: str, ndvi_path: str) -> dict:
    """Compute NDVI from raw B04/B08, write it as GeoTIFF and return its stats."""
    with rasterio.open(raw_path) as src:
        red = src.read(1).astype("float32")
        nir = src.read(2).astype("float32")
        profile = src.profile

    denom = nir + red
    ndvi = np.full(red.shape, np.nan, dtype="float32")
    np.divide(nir - red, denom, out=ndvi, where=denom > 0)

    profile.update(count=1, dtype="float32", nodata=np.nan, compress="deflate", predictor=3)
    os.makedirs(os.path.dirname(ndvi_path) or ".", exist_ok=True)
    with rasterio.open(ndvi_path, "w", **profile) as dst:
        dst.write(ndvi, 1)

    valid = ndvi[~np.isnan(ndvi)]

    # --- SAFETY CHECK FOR EMPTY / CLOUDY SCENES ---
    if valid.size == 0:
        print(f"Warning: No valid pixels found in {raw_path}. Scene may be entirely cloudy or masked out.")
        return {
            "ndvi_mean": float("nan"),
            "ndvi_min": float("nan"),
            "ndvi_max": float("nan"),
            "ndvi_std": float("nan"),
            "valid_pixel_pct": 0.0,
        }

    return {
        "ndvi_mean": float(valid.mean()),
        "ndvi_min": float(valid.min()),
        "ndvi_max": float(valid.max()),
        "ndvi_std": float(valid.std()),
        "valid_pixel_pct": float(100 * valid.size / ndvi.size),
    }
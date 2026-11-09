CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS ndvi_runs (
    id               serial PRIMARY KEY,
    run_at           timestamptz NOT NULL DEFAULT now(),
    acquisition_date date        NOT NULL,
    scene_id         text        NOT NULL UNIQUE,
    cloud_cover      real,
    ndvi_path        text        NOT NULL,
    ndvi_mean        real,
    ndvi_min         real,
    ndvi_max         real,
    ndvi_std         real,
    valid_pixel_pct  real,
    geom             geometry(Polygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS ndvi_runs_date_idx ON ndvi_runs (acquisition_date);
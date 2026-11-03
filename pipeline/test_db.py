import psycopg

with psycopg.connect(
    host="localhost", port=5432,
    dbname="sentinel", user="sentinel", password="sentinel",
) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            chemin TEXT NOT NULL,
            date_acquisition DATE,
            emprise geometry(Polygon, 4326)
        )
    """)
    print(conn.execute("SELECT postgis_version()").fetchone())
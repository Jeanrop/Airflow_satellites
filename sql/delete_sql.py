import psycopg

# Use your connection details or database URL
with psycopg.connect("dbname=your_db user=your_user password=your_password host=localhost") as conn:
    conn.execute("DROP TABLE IF EXISTS ndvi_runs CASCADE;")
    print("Table ndvi_runs deleted successfully.")
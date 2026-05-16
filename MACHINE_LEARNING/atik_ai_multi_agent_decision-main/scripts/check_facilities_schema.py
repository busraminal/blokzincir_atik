from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:admin@localhost:5432/postgre_database')
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'facilities'
        ORDER BY ordinal_position
    """)).fetchall()

    for col, dtype in rows:
        print(f"{col}|{dtype}")

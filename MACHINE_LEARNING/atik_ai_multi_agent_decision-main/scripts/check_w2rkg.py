from sqlalchemy import create_engine, text
import json

engine = create_engine('postgresql://postgres:admin@localhost:5432/postgre_database')
with engine.connect() as conn:

    # Kolon yapısı
    cols = conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='w2rkg_library' ORDER BY ordinal_position"
    )).fetchall()
    print("=== KOLON YAPISI ===")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")

    # İlk 5 satır
    print("\n=== İLK 3 SATIR ===")
    rows = conn.execute(text("SELECT * FROM w2rkg_library LIMIT 3")).fetchall()
    col_names = [c[0] for c in cols]
    for row in rows:
        print("\n---")
        for name, val in zip(col_names, row):
            if val is not None:
                val_str = str(val)[:200]
                print(f"  {name}: {val_str}")

    # Benzersiz değerler
    print("\n=== UNIQUE DEĞERLER (kategorik kolonlar) ===")
    for col_name, col_type in cols:
        if col_type in ('character varying', 'text'):
            try:
                uniq = conn.execute(text(
                    f"SELECT COUNT(DISTINCT {col_name}) FROM w2rkg_library"
                )).scalar()
                if uniq < 50:
                    vals = conn.execute(text(
                        f"SELECT DISTINCT {col_name} FROM w2rkg_library WHERE {col_name} IS NOT NULL LIMIT 20"
                    )).fetchall()
                    print(f"\n  {col_name} ({uniq} unique): {[v[0] for v in vals]}")
                else:
                    print(f"\n  {col_name}: {uniq} unique değer (kategorik değil)")
            except:
                pass

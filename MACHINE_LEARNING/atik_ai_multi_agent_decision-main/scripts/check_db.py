from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:admin@localhost:5432/postgre_database')
with engine.connect() as conn:
    tables = conn.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    )).fetchall()
    print("=== TABLOLAR ===")
    for t in tables:
        print(t[0])

    # w2rkg_library var mı?
    w2rkg_tables = [t[0] for t in tables if 'w2rkg' in t[0].lower() or 'library' in t[0].lower() or 'knowl' in t[0].lower()]
    print("\n=== W2RKG/LIBRARY/KNOWLEDGE TABLOLAR ===")
    print(w2rkg_tables if w2rkg_tables else "YOK")

    # Her tablonun satır sayısı
    print("\n=== SATIR SAYILARI ===")
    for t in tables:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t[0]}")).scalar()
            print(f"{t[0]}: {count} satır")
        except:
            print(f"{t[0]}: erişilemedi")

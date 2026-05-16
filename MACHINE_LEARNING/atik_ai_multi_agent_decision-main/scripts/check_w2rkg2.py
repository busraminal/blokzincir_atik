from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:admin@localhost:5432/postgre_database')
with engine.connect() as conn:

    # Örnek waste tipleri
    print("=== EN SIK WASTE TİPLERİ (Top 20) ===")
    rows = conn.execute(text(
        "SELECT waste, COUNT(*) as cnt FROM w2rkg_library GROUP BY waste ORDER BY cnt DESC LIMIT 20"
    )).fetchall()
    for r in rows:
        print(f"  {r[0][:60]}: {r[1]} kayıt")

    # Örnek resource tipleri
    print("\n=== EN SIK RESOURCE TİPLERİ (Top 20) ===")
    rows = conn.execute(text(
        "SELECT resource, COUNT(*) as cnt FROM w2rkg_library GROUP BY resource ORDER BY cnt DESC LIMIT 20"
    )).fetchall()
    for r in rows:
        print(f"  {r[0][:60]}: {r[1]} kayıt")

    # Metal/kimya gibi endüstriyel atıklar var mı?
    print("\n=== SANAYİ İLE İLGİLİ ÖRNEKler ===")
    keywords = ['metal', 'plastic', 'aluminum', 'steel', 'copper', 'oil', 'slag', 'sludge', 'solvent', 'rubber']
    for kw in keywords:
        cnt = conn.execute(text(
            f"SELECT COUNT(*) FROM w2rkg_library WHERE waste ILIKE '%{kw}%'"
        )).scalar()
        if cnt > 0:
            sample = conn.execute(text(
                f"SELECT waste, resource FROM w2rkg_library WHERE waste ILIKE '%{kw}%' LIMIT 2"
            )).fetchall()
            print(f"\n  [{kw}] → {cnt} kayıt")
            for s in sample:
                print(f"    waste: {s[0][:50]} → resource: {s[1][:50]}")

    # DOI benzersizlik
    print("\n=== VERİ KALİTESİ ===")
    total = conn.execute(text("SELECT COUNT(*) FROM w2rkg_library")).scalar()
    with_doi = conn.execute(text("SELECT COUNT(*) FROM w2rkg_library WHERE doi_reference IS NOT NULL")).scalar()
    papers = conn.execute(text("SELECT COUNT(DISTINCT doi_reference) FROM w2rkg_library")).scalar()
    print(f"  Toplam kayıt: {total}")
    print(f"  DOI olan: {with_doi}")
    print(f"  Benzersiz makale: {papers}")
    print(f"  Ortalama kayıt/makale: {total//papers if papers else 0}")

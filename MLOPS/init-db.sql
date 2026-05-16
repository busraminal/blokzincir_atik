-- ATIK AI — minimal şema + örnek veri (Docker Postgres ilk volume oluşturulduğunda bir kez çalışır)

CREATE TABLE IF NOT EXISTS sectors (
    id SERIAL PRIMARY KEY,
    sector_name VARCHAR(255) NOT NULL,
    nace_code VARCHAR(20),
    description TEXT
);

INSERT INTO sectors (id, sector_name, nace_code, description) VALUES
  (1, 'Metal üretimi', '24', 'Örnek sektör'),
  (2, 'Geri kazanım', '38', 'Örnek sektör'),
  (3, 'Gıda', '10', 'Örnek sektör');

SELECT setval(pg_get_serial_sequence('sectors', 'id'), (SELECT COALESCE(MAX(id), 1) FROM sectors));

CREATE TABLE IF NOT EXISTS facilities (
    id SERIAL PRIMARY KEY,
    facility_name VARCHAR(255) NOT NULL,
    nace_code VARCHAR(50),
    city VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    sector_id INTEGER REFERENCES sectors(id),
    facility_type VARCHAR(100),
    storage_capacity_ton DOUBLE PRECISION,
    activity_text TEXT
);

INSERT INTO facilities (facility_name, nace_code, city, latitude, longitude, sector_id, facility_type, activity_text) VALUES
  ('Demo Metal A.Ş.', '24.10', 'Ankara', 39.9334, 32.8597, 1, 'üretici', 'Çelik hurda ve ambalaj atığı'),
  ('Demo Geri Kazanım', '38.12', 'Ankara', 39.9450, 32.8700, 2, 'bertaraf', 'Ambalaj ve plastik geri dönüşüm'),
  ('Demo Gıda İşl.', '10.11', 'Ankara', 39.9200, 32.8400, 3, 'üretici', 'Organik yan ürün'),
  ('Demo Enerji', '35.11', 'Ankara', 39.9100, 32.9000, 1, 'alıcı', 'Yanmalı atık kabul');

SELECT setval(pg_get_serial_sequence('facilities', 'id'), (SELECT COALESCE(MAX(id), 1) FROM facilities));

CREATE TABLE IF NOT EXISTS waste_types (
    id SERIAL PRIMARY KEY,
    waste_code VARCHAR(20) UNIQUE NOT NULL,
    description TEXT,
    status VARCHAR(50),
    sector_id INTEGER REFERENCES sectors(id)
);

INSERT INTO waste_types (waste_code, description, status, sector_id) VALUES
  ('150106', 'Ambalaj atığı — kağıt/karton', 'aktif', 2),
  ('150110', 'Ambalaj atığı — plastik', 'aktif', 2),
  ('170401', 'Bakır hurda', 'aktif', 1),
  ('170405', 'Demir-çelik hurda', 'aktif', 1),
  ('020106', 'Zararsız toprak/taş', 'aktif', NULL),
  ('200301', 'Karışık belediye atığı', 'aktif', NULL),
  ('020201', 'Gıda işleme atığı (animal)', 'aktif', 3),
  ('150102', 'Plastik ambalaj — PE/PP', 'aktif', 2);

SELECT setval(pg_get_serial_sequence('waste_types', 'id'), (SELECT COALESCE(MAX(id), 1) FROM waste_types));

CREATE TABLE IF NOT EXISTS match_candidates (
    id SERIAL PRIMARY KEY,
    source_facility_id INTEGER NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    receiver_facility_id INTEGER NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    waste_code VARCHAR(20) NOT NULL,
    overall_score DOUBLE PRECISION NOT NULL,
    technical_score DOUBLE PRECISION NOT NULL,
    temporal_score DOUBLE PRECISION NOT NULL,
    distance_score DOUBLE PRECISION NOT NULL,
    distance_km DOUBLE PRECISION NOT NULL,
    rank_order INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO match_candidates (
    source_facility_id, receiver_facility_id, waste_code,
    overall_score, technical_score, temporal_score, distance_score,
    distance_km, rank_order
) VALUES
  (1, 2, '170405', 0.72, 0.85, 0.55, 0.68, 4.2, 1),
  (1, 4, '150110', 0.58, 0.60, 0.50, 0.62, 12.5, 2),
  (3, 2, '020201', 0.65, 0.70, 0.60, 0.64, 8.1, 1);

-- Журнал выбытия комплектов (ТЗ file-012): лауреатам и «иное».
CREATE TABLE IF NOT EXISTS kit_disposals (id SERIAL PRIMARY KEY, award_id INTEGER NOT NULL REFERENCES awards(id) ON DELETE CASCADE, laureate_award_id INTEGER REFERENCES laureate_awards(id) ON DELETE SET NULL, target VARCHAR(20) NOT NULL DEFAULT 'other', event_name VARCHAR(500), reason VARCHAR(500), protocol_number VARCHAR(100), disposal_date DATE, note TEXT, quantity INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_kit_disposals_award ON kit_disposals(award_id);
CREATE INDEX IF NOT EXISTS idx_kit_disposals_target ON kit_disposals(target);
CREATE TABLE IF NOT EXISTS universal_stock (id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1), certificate_count INTEGER NOT NULL DEFAULT 0, box_count INTEGER NOT NULL DEFAULT 0);
INSERT INTO universal_stock (id, certificate_count, box_count) VALUES (1, 0, 0) ON CONFLICT (id) DO NOTHING;

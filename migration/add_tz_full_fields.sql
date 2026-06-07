-- Расширение полей по ТЗ: лауреаты, НК, учреждение, склад (комплекты, украшения)

ALTER TABLE laureates ADD COLUMN IF NOT EXISTS birth_date date;
ALTER TABLE laureates ADD COLUMN IF NOT EXISTS passport varchar(100);
ALTER TABLE laureates ADD COLUMN IF NOT EXISTS inn varchar(20);
ALTER TABLE laureates ADD COLUMN IF NOT EXISTS snils varchar(20);
ALTER TABLE laureates ADD COLUMN IF NOT EXISTS regalia text;
ALTER TABLE laureates ADD COLUMN IF NOT EXISTS photo bytea;

ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS birth_date date;
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS phone_work varchar(100);
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS assistant_name varchar(500);
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS assistant_phone varchar(100);
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS inclusion_protocol_number varchar(50);
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS inclusion_protocol_date date;
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS consent_letter varchar(500);
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS photo_filename varchar(500);

ALTER TABLE award_establishments ADD COLUMN IF NOT EXISTS has_protocol_data boolean DEFAULT false;
ALTER TABLE award_establishments ADD COLUMN IF NOT EXISTS protocol_filename varchar(500);
ALTER TABLE award_establishments ADD COLUMN IF NOT EXISTS protocol_content_type varchar(200);
ALTER TABLE award_establishments ADD COLUMN IF NOT EXISTS protocol_data bytea;

CREATE TABLE IF NOT EXISTS award_kit_stock (
    id SERIAL PRIMARY KEY,
    award_id INTEGER NOT NULL UNIQUE REFERENCES awards(id) ON DELETE CASCADE,
    physical_sets INTEGER DEFAULT 0,
    free_sets INTEGER DEFAULT 0,
    postponed_sets INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS decoration_disposals (
    id SERIAL PRIMARY KEY,
    award_id INTEGER NOT NULL REFERENCES awards(id) ON DELETE CASCADE,
    laureate_award_id INTEGER REFERENCES laureate_awards(id) ON DELETE SET NULL,
    component_type VARCHAR(50) NOT NULL,
    target VARCHAR(20) NOT NULL DEFAULT 'laureate',
    event_name VARCHAR(500),
    reason VARCHAR(500),
    disposal_date DATE,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_decoration_disposals_award ON decoration_disposals(award_id);

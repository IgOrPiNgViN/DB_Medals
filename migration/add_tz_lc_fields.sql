-- Дополнительные поля ЖЦ лауреата по ТЗ (Access: ЛАУР_ЖЦ.csv)
-- Применить к существующей БД: psql -d awards_db -f migration/add_tz_lc_fields.sql

ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS voting_secretariat_done boolean DEFAULT false;
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS voting_secretariat_date date;
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS decision_authorized_ppz varchar(500);
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS registration_extract_number varchar(100);
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS registration_protocol_number varchar(100);
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS registration_pending_issue boolean DEFAULT false;
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS registration_pending_comment text;
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS ceremony_officiant varchar(500);
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS ceremony_kit_type varchar(200);
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS publication_nk_link varchar(500);
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS publication_smi_web_count integer DEFAULT 0;
ALTER TABLE laureate_lifecycles ADD COLUMN IF NOT EXISTS publication_smi_print_count integer DEFAULT 0;

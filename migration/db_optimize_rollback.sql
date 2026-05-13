-- ============================================================
-- ОТКАТ оптимизации db_optimize.sql
-- ============================================================

BEGIN;

-- 5. Убираем enum-колонки
ALTER TABLE laureate_awards    DROP COLUMN IF EXISTS status_enum;
ALTER TABLE award_developments DROP COLUMN IF EXISTS status_enum;
ALTER TABLE award_productions  DROP COLUMN IF EXISTS status_enum;
ALTER TABLE award_approvals    DROP COLUMN IF EXISTS status_enum;

DROP TYPE IF EXISTS laureateawardstatus;
DROP TYPE IF EXISTS developmentstatus;
DROP TYPE IF EXISTS productionstatus;
DROP TYPE IF EXISTS approvalstatus;

-- 4. Убираем индексы
DROP INDEX IF EXISTS idx_lc_publication_done;
DROP INDEX IF EXISTS idx_lc_ceremony_done;
DROP INDEX IF EXISTS idx_lc_registration_done;
DROP INDEX IF EXISTS idx_lc_decision_done;
DROP INDEX IF EXISTS idx_lc_voting_done;
DROP INDEX IF EXISTS idx_lc_nomination_done;
DROP INDEX IF EXISTS idx_awards_type;
DROP INDEX IF EXISTS idx_laureates_category;
DROP INDEX IF EXISTS idx_laureates_created_at;

-- 3. Возвращаем поле bulletin_number в laureate_awards
--    (данные не восстанавливаются автоматически)
ALTER TABLE laureate_awards ADD COLUMN IF NOT EXISTS bulletin_number varchar(50);

-- 2. Убираем check-ограничения
ALTER TABLE award_developments  DROP CONSTRAINT IF EXISTS chk_development_dates;
ALTER TABLE bulletins           DROP CONSTRAINT IF EXISTS chk_bulletin_dates;
ALTER TABLE inventory_items     DROP CONSTRAINT IF EXISTS chk_inventory_counts;
ALTER TABLE inventory_items     DROP CONSTRAINT IF EXISTS chk_inventory_available;

-- 1. Убираем уникальные ограничения
ALTER TABLE member_signing_rights  DROP CONSTRAINT IF EXISTS uq_signing_rights_member_award;
ALTER TABLE bulletin_distributions DROP CONSTRAINT IF EXISTS uq_distribution_bulletin_member;
ALTER TABLE votes                  DROP CONSTRAINT IF EXISTS uq_votes_question_member;

COMMIT;

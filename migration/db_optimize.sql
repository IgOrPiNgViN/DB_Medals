-- ============================================================
-- Оптимизация схемы БД: индексы, уникальные ограничения,
-- удаление дублирующего поля, генерируемая колонка.
--
-- Запускать ОДИН РАЗ на рабочей БД.
-- Откат: db_optimize_rollback.sql
-- ============================================================

BEGIN;

-- ────────────────────────────────────────────────────────────
-- 1. УНИКАЛЬНЫЕ ОГРАНИЧЕНИЯ (отсутствовали на уровне БД)
--    Логика была только в коде → риск дублей при прямых запросах.
-- ────────────────────────────────────────────────────────────

-- Один член НК — один голос за вопрос
ALTER TABLE votes
    ADD CONSTRAINT uq_votes_question_member
    UNIQUE (question_id, member_id);

-- Бюллетень рассылается члену НК только один раз
ALTER TABLE bulletin_distributions
    ADD CONSTRAINT uq_distribution_bulletin_member
    UNIQUE (bulletin_id, member_id);

-- Роль подписанта — уникальна для пары (член, награда)
ALTER TABLE member_signing_rights
    ADD CONSTRAINT uq_signing_rights_member_award
    UNIQUE (member_id, award_id);

-- ────────────────────────────────────────────────────────────
-- 2. CHECK-ОГРАНИЧЕНИЯ
-- ────────────────────────────────────────────────────────────

-- available_count всегда должен совпадать с расчётным значением
ALTER TABLE inventory_items
    ADD CONSTRAINT chk_inventory_available
    CHECK (available_count = total_count - reserve_count - issued_count);

-- Нельзя зарезервировать/выдать больше, чем есть
ALTER TABLE inventory_items
    ADD CONSTRAINT chk_inventory_counts
    CHECK (reserve_count + issued_count <= total_count
       AND reserve_count >= 0
       AND issued_count  >= 0
       AND total_count   >= 0);

-- Дата начала голосования ≤ дата окончания
ALTER TABLE bulletins
    ADD CONSTRAINT chk_bulletin_dates
    CHECK (voting_start IS NULL OR voting_end IS NULL OR voting_start <= voting_end);

-- Дата разработки: начало ≤ конец
ALTER TABLE award_developments
    ADD CONSTRAINT chk_development_dates
    CHECK (start_date IS NULL OR end_date IS NULL OR start_date <= end_date);

-- ────────────────────────────────────────────────────────────
-- 3. УДАЛЕНИЕ ДУБЛИРУЮЩЕГО ПОЛЯ
--    laureate_awards.bulletin_number дублирует
--    laureate_lifecycles.voting_bulletin_number.
--    Единственный источник правды → lifecycle.
--    Данные переносим перед удалением.
-- ────────────────────────────────────────────────────────────

-- Перенести данные: если в lifecycle пусто, взять из laureate_awards
UPDATE laureate_lifecycles lc
SET    voting_bulletin_number = la.bulletin_number
FROM   laureate_awards la
WHERE  la.id = lc.laureate_award_id
  AND  (lc.voting_bulletin_number IS NULL OR lc.voting_bulletin_number = '')
  AND  la.bulletin_number IS NOT NULL
  AND  la.bulletin_number <> '';

-- Удаляем дублирующую колонку
ALTER TABLE laureate_awards DROP COLUMN IF EXISTS bulletin_number;

-- ────────────────────────────────────────────────────────────
-- 4. ИНДЕКСЫ НА ЧАСТО ФИЛЬТРУЕМЫХ КОЛОНКАХ
-- ────────────────────────────────────────────────────────────

-- Отчёт «незавершённый ЖЦ» — фильтр по флагам этапов
CREATE INDEX IF NOT EXISTS idx_lc_nomination_done  ON laureate_lifecycles (nomination_done);
CREATE INDEX IF NOT EXISTS idx_lc_voting_done      ON laureate_lifecycles (voting_done);
CREATE INDEX IF NOT EXISTS idx_lc_decision_done    ON laureate_lifecycles (decision_done);
CREATE INDEX IF NOT EXISTS idx_lc_registration_done ON laureate_lifecycles (registration_done);
CREATE INDEX IF NOT EXISTS idx_lc_ceremony_done    ON laureate_lifecycles (ceremony_done);
CREATE INDEX IF NOT EXISTS idx_lc_publication_done ON laureate_lifecycles (publication_done);

-- Фильтрация наград по типу
CREATE INDEX IF NOT EXISTS idx_awards_type ON awards (award_type);

-- Фильтрация лауреатов по категории
CREATE INDEX IF NOT EXISTS idx_laureates_category ON laureates (category);

-- Поиск по дате создания в статистических отчётах
CREATE INDEX IF NOT EXISTS idx_laureates_created_at ON laureates (created_at);

-- ────────────────────────────────────────────────────────────
-- 5. НОРМАЛИЗАЦИЯ «СТАТУСНЫХ» ПОЛЕЙ
--    В award_approvals.status, award_productions.status,
--    award_developments.status, laureate_awards.status
--    сейчас varchar — свободный текст.
--    Добавляем enum-типы и колонки рядом (старые пока оставляем).
-- ────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE approvalstatus AS ENUM ('pending','approved','rejected','revision');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE productionstatus AS ENUM ('planned','ordered','in_production','delivered','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE developmentstatus AS ENUM ('planned','in_progress','review','completed','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE laureateawardstatus AS ENUM ('nominated','approved','rejected','awarded','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Добавляем типизированные колонки рядом со старыми (миграция данных — ручная)
ALTER TABLE award_approvals
    ADD COLUMN IF NOT EXISTS status_enum approvalstatus;

ALTER TABLE award_productions
    ADD COLUMN IF NOT EXISTS status_enum productionstatus;

ALTER TABLE award_developments
    ADD COLUMN IF NOT EXISTS status_enum developmentstatus;

ALTER TABLE laureate_awards
    ADD COLUMN IF NOT EXISTS status_enum laureateawardstatus;

COMMIT;

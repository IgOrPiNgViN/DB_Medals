-- НК: неголосующий, фото (bytea)
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS is_non_voting boolean DEFAULT false;
ALTER TABLE committee_members ADD COLUMN IF NOT EXISTS photo bytea;

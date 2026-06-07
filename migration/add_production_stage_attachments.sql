CREATE TABLE IF NOT EXISTS production_stage_attachments (
  id SERIAL PRIMARY KEY,
  stage_row_id INTEGER NOT NULL REFERENCES production_stage_rows(id) ON DELETE CASCADE,
  filename VARCHAR(500) NOT NULL,
  content_type VARCHAR(200),
  data BYTEA NOT NULL,
  uploaded_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_prod_stage_att_row ON production_stage_attachments(stage_row_id);

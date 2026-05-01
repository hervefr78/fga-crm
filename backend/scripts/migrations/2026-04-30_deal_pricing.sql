-- FGA CRM — Migration : ajout pricing recurrent sur deals
-- Run : docker exec -i fga-crm-db psql -U postgres -d fgacrm < this_file.sql

ALTER TABLE deals ADD COLUMN IF NOT EXISTS pricing_type VARCHAR(20) NOT NULL DEFAULT 'one_shot';
ALTER TABLE deals ADD COLUMN IF NOT EXISTS recurring_amount DOUBLE PRECISION;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS commitment_months INTEGER;

CREATE INDEX IF NOT EXISTS ix_deals_pricing_type ON deals(pricing_type);

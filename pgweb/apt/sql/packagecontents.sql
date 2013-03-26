CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX apt_packagecontents_filename_gin ON apt_packagecontents USING gin (filename gin_trgm_ops);

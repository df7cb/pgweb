CREATE EXTENSION IF NOT EXISTS debversion;
ALTER TABLE apt_source ALTER COLUMN srcversion TYPE debversion;

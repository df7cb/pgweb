CREATE EXTENSION IF NOT EXISTS debversion;
ALTER TABLE apt_package ALTER COLUMN version type debversion;

-- Create additional databases for mautrix bridges.
-- This script runs on first postgres-mautrix init.
-- For existing deployments, run manually:
--   CREATE DATABASE mautrix_meta_facebook;
--   CREATE DATABASE mautrix_meta_instagram;
--   CREATE DATABASE mautrix_linkedin;

SELECT 'Creating mautrix_meta_facebook' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mautrix_meta_facebook');
CREATE DATABASE mautrix_meta_facebook;

SELECT 'Creating mautrix_meta_instagram' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mautrix_meta_instagram');
CREATE DATABASE mautrix_meta_instagram;

SELECT 'Creating mautrix_linkedin' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mautrix_linkedin');
CREATE DATABASE mautrix_linkedin;

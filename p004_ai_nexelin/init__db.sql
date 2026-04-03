CREATE EXTENSION IF NOT EXISTS vector;

-- Langflow database
SELECT 'CREATE DATABASE langflow_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langflow_db')\gexec
#!/bin/bash
set -e

# Create additional databases for Matrix services
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE synapse'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'synapse')\gexec

    SELECT 'CREATE DATABASE mautrix_whatsapp'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mautrix_whatsapp')\gexec
EOSQL

echo "Matrix databases created successfully"

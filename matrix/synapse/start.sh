#!/bin/sh
set -e

# Substitute environment variables in homeserver template
python3 << 'PYEOF'
import os, re

with open('/config/homeserver.yaml') as f:
    content = f.read()

def replace_var(m):
    var = m.group(1)
    default = m.group(2) if m.group(2) is not None else ''
    return os.environ.get(var, default)

# Match ${VAR:-default} and ${VAR} patterns
content = re.sub(r'\$\{(\w+)(?::-(.*?))?\}', replace_var, content)

# Check if whatsapp-registration.yaml exists
# If not, remove app_service_config_files to allow Synapse to start without it
reg_path = '/data/whatsapp-registration.yaml'
if not os.path.exists(reg_path):
    # Check if mautrix-whatsapp generated it in its data dir
    mautrix_reg = '/mautrix-data/registration.yaml'
    if os.path.exists(mautrix_reg):
        import shutil
        shutil.copy2(mautrix_reg, reg_path)
        print(f'Copied registration from {mautrix_reg} to {reg_path}')
    else:
        # Remove appservice config so Synapse can start without it
        lines = content.split('\n')
        filtered = []
        skip_next = False
        for line in lines:
            if 'app_service_config_files' in line:
                skip_next = True
                continue
            if skip_next and line.strip().startswith('- '):
                continue
            skip_next = False
            filtered.append(line)
        content = '\n'.join(filtered)
        print('WARNING: No whatsapp registration found, starting without appservice')

with open('/data/homeserver.yaml', 'w') as f:
    f.write(content)
print('homeserver.yaml generated from template')
PYEOF

# Ensure synapse databases exist (init-databases.sh only runs on first PG init)
python3 << 'DBEOF'
import os
try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    pg_user = os.environ.get('POSTGRES_USER', 'postgres')
    pg_pass = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    conn = psycopg2.connect(host='postgres', port=5432, user=pg_user, password=pg_pass, dbname='postgres')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    for db_name in ('synapse', 'mautrix_whatsapp'):
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            cur.execute(
                "CREATE DATABASE %s OWNER %s ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0"
                % (db_name, pg_user)
            )
            print('Created database: %s' % db_name)
        else:
            print('Database exists: %s' % db_name)
    cur.close()
    conn.close()
except Exception as e:
    print('WARNING: Could not ensure databases: %s' % e)
DBEOF

# Copy log config if not in /data
if [ ! -f /data/crm.local.log.config ]; then
    cp /config/crm.local.log.config /data/crm.local.log.config
    echo "Log config copied to /data"
fi

# Generate signing key if not exists
if [ ! -f /data/crm.local.signing.key ]; then
    python3 -m synapse.app.homeserver --generate-keys -c /data/homeserver.yaml
    echo "Signing key generated"
fi

# Fix permissions — Synapse runs as UID 991
chown -R 991:991 /data

# Start via original entrypoint
exec /start.py

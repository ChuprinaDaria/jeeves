#!/usr/bin/env bash
# Bootstrap a mautrix bridge: copy config.yaml.example -> config.yaml,
# fill in synapse domain + fresh AS/HS tokens, generate the appservice
# registration.yaml. Stops short of editing homeserver.yaml or starting
# the bridge — that is a deliberate manual step (it requires Synapse
# restart and a quick visual review of the generated registration).
#
# Usage:  ./bin/bootstrap-bridge.sh <telegram|whatsapp|meta>
#
# Run from infra/matrix/ — or any subdir; the script auto-locates its
# repo root.

set -euo pipefail

BRIDGE="${1:-}"
case "$BRIDGE" in
  telegram|whatsapp|meta) ;;
  *)
    echo "usage: $0 <telegram|whatsapp|meta>" >&2
    exit 64
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MATRIX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$MATRIX_ROOT"

if [[ ! -f .env ]]; then
  echo ".env not found in $MATRIX_ROOT — copy .env.example first." >&2
  exit 65
fi

# shellcheck disable=SC1091
set -a
. ./.env
set +a

if [[ -z "${MATRIX_DOMAIN:-}" ]]; then
  echo "MATRIX_DOMAIN is not set in .env" >&2
  exit 66
fi

BRIDGE_SLUG="mautrix-$BRIDGE"
BRIDGE_DIR="bridges/$BRIDGE_SLUG"
EXAMPLE="$BRIDGE_DIR/config.yaml.example"
CONFIG="$BRIDGE_DIR/config.yaml"
REG="$BRIDGE_DIR/registration.yaml"

if [[ ! -f "$EXAMPLE" ]]; then
  echo "missing $EXAMPLE — is the bridge directory checked into the repo?" >&2
  exit 67
fi

if [[ ! -f "$CONFIG" ]]; then
  cp "$EXAMPLE" "$CONFIG"
  echo "copied $EXAMPLE → $CONFIG"
else
  echo "$CONFIG already exists — leaving as-is (delete it to re-bootstrap)."
fi

AS_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
HS_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Simple in-place edits — works for the example layout we ship.
python3 - "$CONFIG" "$MATRIX_DOMAIN" "$AS_TOKEN" "$HS_TOKEN" <<'PY'
import re, sys
path, domain, as_tok, hs_tok = sys.argv[1:]
text = open(path).read()
text = re.sub(r'^( *domain:).*$', r'\1 ' + domain, text, count=1, flags=re.M)
text = re.sub(r'(as_token:)\s*\S+', r'\1 ' + as_tok, text, count=1)
text = re.sub(r'(hs_token:)\s*\S+', r'\1 ' + hs_tok, text, count=1)
open(path, 'w').write(text)
PY

echo "patched domain + tokens in $CONFIG"

echo "Generating registration via docker compose run (bridge container)..."
docker compose --env-file .env run --rm "$BRIDGE_SLUG" \
  -g -c /data/config.yaml -r /data/registration.yaml || {
    echo "registration generation failed — check container logs above" >&2
    exit 1
}

if [[ ! -f "$REG" ]]; then
  echo "expected $REG but it was not created" >&2
  exit 1
fi

cat <<MSG

✓ Bridge bootstrap complete for $BRIDGE_SLUG.

Next manual steps:

  1. Edit synapse/homeserver.yaml and add (under app_service_config_files):
       - /data/$BRIDGE_SLUG-registration.yaml

  2. Mount the registration into synapse — append to docker-compose.yml under
     the synapse service's 'volumes:' list:
       - ./bridges/$BRIDGE_SLUG/registration.yaml:/data/$BRIDGE_SLUG-registration.yaml:ro

  3. Restart synapse, then start the bridge:
       docker compose --env-file .env up -d synapse
       docker compose --env-file .env up -d $BRIDGE_SLUG

  4. From Element, DM @${BRIDGE}bot:$MATRIX_DOMAIN to log in.

MSG

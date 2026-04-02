#!/bin/bash
set -e

BRIDGES=("mautrix-whatsapp:whatsapp" "mautrix-meta-facebook:meta-facebook" "mautrix-meta-instagram:meta-instagram" "mautrix-linkedin:linkedin")

for entry in "${BRIDGES[@]}"; do
    IFS=':' read -r container name <<< "$entry"
    SRC="./${container}/registration.yaml"
    DST="./synapse/${name}-registration.yaml"

    if [ ! -f "$SRC" ]; then
        echo "WARNING: $SRC not found. Start $container first to generate it."
        continue
    fi

    cp "$SRC" "$DST"
    echo "Copied $SRC -> $DST"
done

echo ""
echo "Done. Now restart Synapse: docker compose restart synapse"

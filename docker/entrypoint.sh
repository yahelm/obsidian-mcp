#!/bin/bash
set -e

if [ -n "$SSH_PRIVATE_KEY" ]; then
    mkdir -p /root/.ssh
    echo "$SSH_PRIVATE_KEY" | base64 -d > /root/.ssh/id_ed25519
    chmod 600 /root/.ssh/id_ed25519
fi

exec "$@"

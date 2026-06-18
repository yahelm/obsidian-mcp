#!/bin/bash
set -e

if [ -n "$SSH_PRIVATE_KEY" ]; then
    mkdir -p /tmp/.ssh
    echo "$SSH_PRIVATE_KEY" | base64 -d > /tmp/.ssh/id_ed25519
    chmod 600 /tmp/.ssh/id_ed25519
fi

exec "$@"

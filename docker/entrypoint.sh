#!/bin/bash
set -e

if [ -n "$SSH_PRIVATE_KEY" ]; then
    mkdir -p /tmp/.ssh
    echo "$SSH_PRIVATE_KEY" | base64 -d > /tmp/.ssh/id_ed25519
    chmod 600 /tmp/.ssh/id_ed25519
fi

git config --global safe.directory /vault
git config --global user.name "${GIT_USER:-yahelm}"
git config --global user.email "${GIT_EMAIL:-vladmelekh@gmail.com}"
git config --global core.sshCommand "ssh -i /tmp/.ssh/id_ed25519 -o StrictHostKeyChecking=no"

exec "$@"

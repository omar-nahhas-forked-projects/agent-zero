#!/bin/bash

echo "Running initialization script (non-root)..."

# branch from parameter
if [ -z "$1" ]; then
    echo "Error: Branch parameter is empty. Please provide a valid branch name."
    exit 1
fi
BRANCH="$1"

# Copy persistent files to user-writable locations (skip system dirs)
if [ -d /per ]; then
    cp -rn --no-preserve=ownership,mode /per/* "$HOME/" 2>/dev/null || true
fi

# Set up shell profile
touch "$HOME/.bashrc" "$HOME/.profile" 2>/dev/null || true

# update package list in background (via sudo)
sudo apt-get update > /dev/null 2>&1 &

# ─── Init hooks: run /opt/init-*.sh on every container start ─────────
# Mount custom init scripts via docker-compose volumes to /opt/init-*.sh
# They run on every container start, useful for:
#   - Restoring SSH/GPG keys from secrets
#   - Installing runtime dependencies
#   - Any setup that must survive container recreation
for hook in /opt/init-*.sh; do
    [ -e "$hook" ] || continue
    echo "Running init hook: $hook"
    bash "$hook" || echo "⚠ $hook failed (non-fatal)"
done
# ─────────────────────────────────────────────────────────────────────

# let supervisord handle the services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

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

# update package list (must complete before init hooks that install packages)
sudo apt-get update > /dev/null 2>&1

# ─── Init hooks: run /opt/init-*.sh on every container start ─────────
# Mount custom init scripts via docker-compose volumes to /opt/init-*.sh
# They run alphabetically on every container start.
# Use naming to control order (e.g. gpg < model < packages < repos < secrets < ssh).
for hook in /opt/init-*.sh; do
    [ -e "$hook" ] || continue
    echo "Running init hook: $hook"
    bash "$hook" || echo "⚠ $hook failed (non-fatal)"
done
# ─────────────────────────────────────────────────────────────────────

# ─── Launch supervisord ──────────────────────────────────────────────
# If an entrypoint wrapper is mounted, delegate to it so the operator
# can wrap the main process (e.g. direnv, env injection, tracing)
# without rebuilding the image.  Otherwise run supervisord directly.
SUPERVISORD_CMD="/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"

if [ -x /opt/entrypoint-wrapper.sh ]; then
    echo "Delegating to entrypoint wrapper..."
    exec /opt/entrypoint-wrapper.sh $SUPERVISORD_CMD
else
    exec $SUPERVISORD_CMD
fi

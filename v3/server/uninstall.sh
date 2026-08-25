#!/bin/bash
set -e

VENV_DIR="$HOME/.nspire-ai-venv"
ENV_FILE="$HOME/.nspire-ai-env"
PLIST_DST="$HOME/Library/LaunchAgents/com.nspire-ai.proxy.plist"
MDNS_DST="$HOME/Library/LaunchAgents/com.nspire-ai.mdns.plist"

echo "=== nspire-ai-proxy uninstaller ==="
echo ""

# Unload launchd daemons
if [ -f "$PLIST_DST" ]; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm "$PLIST_DST"
    echo "Removed proxy daemon"
fi

if [ -f "$MDNS_DST" ]; then
    launchctl unload "$MDNS_DST" 2>/dev/null || true
    rm "$MDNS_DST"
    echo "Removed mDNS daemon"
fi

# Remove venv
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo "Removed Python environment"
fi

# Ask about env file (contains API key)
if [ -f "$ENV_FILE" ]; then
    read -p "Remove API key file ($ENV_FILE)? (y/N): " remove_env
    if [ "$remove_env" = "y" ] || [ "$remove_env" = "Y" ]; then
        rm "$ENV_FILE"
        echo "Removed API key file"
    else
        echo "Kept API key file"
    fi
fi

echo ""
echo "Uninstall complete."

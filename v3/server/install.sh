#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/.nspire-ai-venv"
ENV_FILE="$HOME/.nspire-ai-env"
PLIST_SRC="$SCRIPT_DIR/com.nspire-ai.proxy.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.nspire-ai.proxy.plist"
MDNS_SRC="$SCRIPT_DIR/com.nspire-ai.mdns.plist"
MDNS_DST="$HOME/Library/LaunchAgents/com.nspire-ai.mdns.plist"
LOG_FILE="$HOME/Library/Logs/nspire-ai-proxy.log"

echo "=== nspire-ai-proxy installer ==="
echo ""

# 1. Get API key
if [ -f "$ENV_FILE" ]; then
    echo "Found existing env file: $ENV_FILE"
    source "$ENV_FILE"
    echo "Current API key: ${GROQ_API_KEY:0:10}..."
    read -p "Keep existing key? (Y/n): " keep_key
    if [ "$keep_key" = "n" ] || [ "$keep_key" = "N" ]; then
        read -p "Enter your Groq API key: " api_key
        echo "export GROQ_API_KEY=\"$api_key\"" > "$ENV_FILE"
    fi
else
    read -p "Enter your Groq API key (https://console.groq.com/keys): " api_key
    if [ -z "$api_key" ]; then
        echo "ERROR: API key is required. Get your free key at https://console.groq.com/keys"
        exit 1
    fi
    echo "export GROQ_API_KEY=\"$api_key\"" > "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

# 2. Create virtual environment
echo ""
echo "Setting up Python environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# Copy server script into venv for self-contained deployment
cp "$SCRIPT_DIR/proxy_server.py" "$VENV_DIR/proxy_server.py"

echo "Python dependencies installed."

# 3. Install launchd plists
echo ""
echo "Installing launchd daemons..."

mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing if present
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl unload "$MDNS_DST" 2>/dev/null || true

# Proxy server plist — replace __HOME__ placeholder
sed "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"

# mDNS advertisement plist (so ESP32 can find us via nspire-proxy.local)
cp "$MDNS_SRC" "$MDNS_DST"

# 4. Start both daemons
launchctl load "$PLIST_DST"
launchctl load "$MDNS_DST"

echo ""
echo "=== Installation complete ==="
echo ""
echo "  Server:  http://0.0.0.0:8080"
echo "  Health:  curl http://localhost:8080/health"
echo "  Logs:    tail -f $LOG_FILE"
echo "  mDNS:    nspire-proxy.local:8080"
echo ""
echo "  The server will auto-start on login and keep running with the lid closed."
echo "  caffeinate prevents sleep while the server is running."
echo ""
echo "  To stop:      launchctl unload $PLIST_DST"
echo "  To restart:   launchctl unload $PLIST_DST && launchctl load $PLIST_DST"
echo "  To uninstall: ./uninstall.sh"
echo ""
echo "Done! The proxy server is running."

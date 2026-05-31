#!/bin/bash
# Zoolog PWA persistent server. Launched at login by the LaunchAgent
# ~/Library/LaunchAgents/org.dmd.zoolog-pwa.plist (KeepAlive restarts it).
#
# Serves this directory on 127.0.0.1:PORT only; the phone reaches it through the
# Tailscale HTTPS proxy (https://<machine>.<tailnet>.ts.net). tailscaled persists
# the serve config across reboots itself, but we re-assert it here as a safety net.
set -u
PORT=8123
DIR="$(cd "$(dirname "$0")" && pwd)"

# Best-effort: (re)point the Tailscale HTTPS proxy at the local server. Non-fatal
# if tailscaled isn't ready yet (it restores its own serve config anyway).
for ts in /opt/homebrew/bin/tailscale /usr/local/bin/tailscale \
          "/Applications/Tailscale.app/Contents/MacOS/Tailscale"; do
  if [ -x "$ts" ]; then
    "$ts" serve --bg "http://127.0.0.1:${PORT}" >/dev/null 2>&1 || true
    break
  fi
done

exec /usr/bin/python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR"

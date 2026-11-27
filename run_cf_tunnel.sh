#!/bin/bash
# Expose the local HTTP server through a named Cloudflare tunnel.
# Requires `cloudflared` on PATH: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
set -euo pipefail
cloudflared tunnel --config ./.cloudflared/config.yml --origincert "${CLOUDFLARED_CERT:-/workspace/.cloudflared/cert.pem}" run

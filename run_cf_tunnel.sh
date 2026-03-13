#!/bin/bash
./cloudflared tunnel  --config ./.cloudflared/config.yml  -origincert /workspace/.cloudflared/cert.pem run
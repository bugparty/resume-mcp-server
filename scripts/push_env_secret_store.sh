#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"
NAMESPACE="${2:-resume-mcp}"
TARGET_SECRET_NAME="${3:-resume-mcp-secrets}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not found in PATH." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NAMESPACE" create secret generic "$TARGET_SECRET_NAME" \
  --from-env-file="$ENV_FILE" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Pushed $ENV_FILE to Kubernetes Secret: $NAMESPACE/$TARGET_SECRET_NAME"

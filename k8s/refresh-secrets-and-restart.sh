#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Refresh Kubernetes Secret from .env and restart deployment pods.

Usage:
  refresh-secrets-and-restart.sh [options]

Options:
  -e, --env-file <path>      Path to .env file
                             default: /home/ubuntu/k8s-deployments/resume-mcp-server/.env
  -n, --namespace <name>     Kubernetes namespace (default: resume-mcp)
  -s, --secret <name>        Secret name (default: resume-mcp-secrets)
  -d, --deployment <name>    Deployment name (default: resume-mcp-server)
  -k, --kubectl-cmd <cmd>    kubectl command prefix
                             default: "sudo k0s kubectl"
      --force-recreate       Delete and recreate secret instead of apply
      --no-restart           Update secret only, do not restart deployment
      --timeout <seconds>    Rollout timeout in seconds (default: 240)
  -h, --help                 Show this help

Examples:
  ./refresh-secrets-and-restart.sh
  ./refresh-secrets-and-restart.sh --force-recreate
  ./refresh-secrets-and-restart.sh -e ./my.env -n resume-mcp
USAGE
}

ENV_FILE="/home/ubuntu/k8s-deployments/resume-mcp-server/.env"
NAMESPACE="resume-mcp"
SECRET_NAME="resume-mcp-secrets"
DEPLOYMENT_NAME="resume-mcp-server"
KUBECTL_CMD="sudo k0s kubectl"
FORCE_RECREATE="false"
NO_RESTART="false"
TIMEOUT_SECONDS="240"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    -n|--namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    -s|--secret)
      SECRET_NAME="$2"
      shift 2
      ;;
    -d|--deployment)
      DEPLOYMENT_NAME="$2"
      shift 2
      ;;
    -k|--kubectl-cmd)
      KUBECTL_CMD="$2"
      shift 2
      ;;
    --force-recreate)
      FORCE_RECREATE="true"
      shift
      ;;
    --no-restart)
      NO_RESTART="true"
      shift
      ;;
    --timeout)
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --timeout must be an integer number of seconds" >&2
  exit 1
fi

run_kubectl() {
  # shellcheck disable=SC2086
  $KUBECTL_CMD "$@"
}

echo "[1/4] Updating secret '$SECRET_NAME' in namespace '$NAMESPACE' from '$ENV_FILE'..."
if [[ "$FORCE_RECREATE" == "true" ]]; then
  run_kubectl -n "$NAMESPACE" delete secret "$SECRET_NAME" --ignore-not-found=true
  run_kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" --from-env-file="$ENV_FILE"
else
  run_kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
    --from-env-file="$ENV_FILE" \
    --dry-run=client -o yaml | run_kubectl apply -f -
fi

if [[ "$NO_RESTART" == "true" ]]; then
  echo "[2/4] Restart skipped (--no-restart)."
  echo "Done."
  exit 0
fi

echo "[2/4] Restarting deployment '$DEPLOYMENT_NAME'..."
run_kubectl -n "$NAMESPACE" rollout restart deploy/"$DEPLOYMENT_NAME"

echo "[3/4] Waiting for rollout to complete (timeout: ${TIMEOUT_SECONDS}s)..."
run_kubectl -n "$NAMESPACE" rollout status deploy/"$DEPLOYMENT_NAME" --timeout="${TIMEOUT_SECONDS}s"

echo "[4/4] Current pods and secret timestamp:"
run_kubectl -n "$NAMESPACE" get pods -l app="$DEPLOYMENT_NAME" -o wide
run_kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='name={.metadata.name} created={.metadata.creationTimestamp}{"\n"}'

echo "Done."

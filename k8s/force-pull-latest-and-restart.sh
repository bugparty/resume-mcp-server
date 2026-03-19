#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Force pull latest image and restart deployment pods.

Usage:
  force-pull-latest-and-restart.sh [options]

Options:
  -n, --namespace <name>      Kubernetes namespace (default: resume-mcp)
  -d, --deployment <name>     Deployment name (default: resume-mcp-server)
  -c, --container <name>      Container name in deployment (default: resume-mcp-server)
  -i, --image <image:tag>     Image to set (default: ghcr.io/bugparty/resume-mcp-server:latest)
  -k, --kubectl-cmd <cmd>     kubectl command prefix (default: "sudo k0s kubectl")
      --delete-pods           Delete existing pods after restart to force immediate recreation
      --timeout <seconds>     Rollout timeout in seconds (default: 240)
  -h, --help                  Show this help

Examples:
  ./force-pull-latest-and-restart.sh
  ./force-pull-latest-and-restart.sh --delete-pods
  ./force-pull-latest-and-restart.sh -i ghcr.io/bugparty/resume-mcp-server:latest
USAGE
}

NAMESPACE="resume-mcp"
DEPLOYMENT_NAME="resume-mcp-server"
CONTAINER_NAME="resume-mcp-server"
IMAGE="ghcr.io/bugparty/resume-mcp-server:latest"
KUBECTL_CMD="sudo k0s kubectl"
DELETE_PODS="false"
TIMEOUT_SECONDS="240"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    -d|--deployment)
      DEPLOYMENT_NAME="$2"
      shift 2
      ;;
    -c|--container)
      CONTAINER_NAME="$2"
      shift 2
      ;;
    -i|--image)
      IMAGE="$2"
      shift 2
      ;;
    -k|--kubectl-cmd)
      KUBECTL_CMD="$2"
      shift 2
      ;;
    --delete-pods)
      DELETE_PODS="true"
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

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --timeout must be an integer number of seconds" >&2
  exit 1
fi

run_kubectl() {
  # shellcheck disable=SC2086
  $KUBECTL_CMD "$@"
}

echo "[1/6] Setting image to '$IMAGE'..."
run_kubectl -n "$NAMESPACE" set image deploy/"$DEPLOYMENT_NAME" "$CONTAINER_NAME"="$IMAGE"

echo "[2/6] Forcing imagePullPolicy=Always..."
run_kubectl -n "$NAMESPACE" patch deploy "$DEPLOYMENT_NAME" \
  -p "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"$CONTAINER_NAME\",\"imagePullPolicy\":\"Always\"}]}}}}"

echo "[3/6] Restarting deployment..."
run_kubectl -n "$NAMESPACE" rollout restart deploy/"$DEPLOYMENT_NAME"

if [[ "$DELETE_PODS" == "true" ]]; then
  echo "[4/6] Deleting existing pods to force immediate recreation..."
  run_kubectl -n "$NAMESPACE" delete pod -l app="$DEPLOYMENT_NAME" --wait=false
else
  echo "[4/6] Skip pod deletion (use --delete-pods to enable)."
fi

echo "[5/6] Waiting for rollout to complete (timeout: ${TIMEOUT_SECONDS}s)..."
run_kubectl -n "$NAMESPACE" rollout status deploy/"$DEPLOYMENT_NAME" --timeout="${TIMEOUT_SECONDS}s"

echo "[6/6] Verifying running pods and image IDs..."
run_kubectl -n "$NAMESPACE" get pods -l app="$DEPLOYMENT_NAME" -o wide
run_kubectl -n "$NAMESPACE" describe pod -l app="$DEPLOYMENT_NAME" | rg -n "^Name:|Image:|Image ID:|Ready:|Started:" -S || true

echo "Done."

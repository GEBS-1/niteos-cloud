#!/usr/bin/env bash
# Pull production cloud_data for fine-tune dataset export.
# Usage:
#   bash finetune/pull_prod_cloud_data.sh
#   bash finetune/pull_prod_cloud_data.sh user@host /path/to/key
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${1:-root@194.226.187.101}"
KEY="${2:-$ROOT/deploy/niteos_deploy_key}"
OUT_TAR="$ROOT/finetune/data/prod_cloud_data.tar.gz"
REMOTE_DIR="${REMOTE_CLOUD_DATA:-/opt/niteos-cloud/cloud_data}"

mkdir -p "$ROOT/finetune/data"
echo "Archiving $REMOTE_DIR on $HOST ..."
ssh -i "$KEY" -o StrictHostKeyChecking=no "$HOST" \
  "tar czf - -C $(dirname "$REMOTE_DIR") $(basename "$REMOTE_DIR")" > "$OUT_TAR"
echo "Saved $OUT_TAR"
echo "Export with:"
echo "  python -m finetune.export_dataset --from-prod-tarball $OUT_TAR"

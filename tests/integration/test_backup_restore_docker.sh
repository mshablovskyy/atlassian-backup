#!/usr/bin/env bash
# End-to-end integration test using Docker: backup a page tree, create a fresh space, restore into it.
#
# Usage:
#   bash tests/integration/test_backup_restore_docker.sh
#   make docker-test-e2e
#
# Prerequisites:
#   - Docker installed and running
#   - Confluence DC running at the URLs configured below
#   - .envBackupSource file with CONFLUENCE_BASE and CONFLUENCE_TOKEN for the source instance
#   - .envRecoveryTarget file with CONFLUENCE_BASE and CONFLUENCE_TOKEN for the target instance
#   - make sure to update BACKUP_URL(line 21)
#   - Docker image built (or will be built automatically)
#
# The backup reads from the source instance and the restore writes to the target instance.
# These can be the same instance (use identical env files) or different ones.

set -euo pipefail

BACKUP_URL="http://192.168.1.177:8090/spaces/ORIGINALCONTENT/pages/6032735/Content+for+validation"
BACKUP_ENV_FILE=".envBackupSource"
RECOVERY_ENV_FILE=".envRecoveryTarget"
SPACE_PREFIX="RESTORETEST"
DELETE_TEST_SPACE=false       #[true|false] Set to false to keep the test space for manual inspection after the test
RESOLVE_USERKEYS=true         #[true|false] Set to true to resolve user mentions during restore
NO_STORE_RAW_RESPONSE=false   #[true|false] Set to true to remove raw_response.json files from backup

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ── Helpers ──────────────────────────────────────────────────────────

step() { printf "\n\033[1;34m==> %s\033[0m\n" "$1"; }
ok()   { printf "\033[1;32m  OK: %s\033[0m\n" "$1"; }
fail() { printf "\033[1;31m  FAIL: %s\033[0m\n" "$1"; exit 1; }

# Parse a .env file and export CONFLUENCE_BASE and CONFLUENCE_TOKEN from it.
# Usage: load_env <file> <base_var> <token_var>
load_env() {
    local env_file="$1" base_var="$2" token_var="$3"
    local _base="" _token=""

    if [[ ! -f "$env_file" ]]; then
        fail "Env file not found: $env_file"
    fi

    while IFS='=' read -r key value; do
        key="$(echo "$key" | xargs)"
        value="$(echo "$value" | sed 's/^["'\''"]//;s/["'\''"]$//' | xargs)"
        case "$key" in
            CONFLUENCE_BASE)  _base="$value" ;;
            CONFLUENCE_TOKEN) _token="$value" ;;
        esac
    done < <(grep -v '^\s*#' "$env_file" | grep -v '^\s*$')

    _base="${_base%/}"

    if [[ -z "$_base" || -z "$_token" ]]; then
        fail "CONFLUENCE_BASE and CONFLUENCE_TOKEN must be set in $env_file"
    fi

    eval "$base_var='$_base'"
    eval "$token_var='$_token'"
}

# ── Step 1: Load configuration ──────────────────────────────────────

step "Loading backup source configuration from $BACKUP_ENV_FILE"
load_env "$BACKUP_ENV_FILE" BACKUP_BASE BACKUP_TOKEN
ok "Backup source: $BACKUP_BASE"

step "Loading recovery target configuration from $RECOVERY_ENV_FILE"
load_env "$RECOVERY_ENV_FILE" RECOVERY_BASE RECOVERY_TOKEN
ok "Recovery target: $RECOVERY_BASE"

# ── Step 2: Build Docker image ──────────────────────────────────────

step "Building Docker image"

make docker-build
ok "Image built"

# ── Step 3: Run backup in Docker (from source instance) ──────────────

step "Running backup from source instance in Docker"

BACKUP_ARGS="--verbose"
if [[ "$NO_STORE_RAW_RESPONSE" == "true" ]]; then
    BACKUP_ARGS="$BACKUP_ARGS --no-store-raw-response"
fi
make docker-backup URL="$BACKUP_URL" ENV_FILE="$BACKUP_ENV_FILE" ARGS="$BACKUP_ARGS"
ok "Backup completed"

# ── Step 4: Find the latest backup directory ────────────────────────

step "Locating backup directory"

BACKUP_DIR="$(ls -dt output/confluence-export-* 2>/dev/null | head -1)"
if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
    fail "No backup directory found in output/"
fi
ok "Backup directory: $BACKUP_DIR"

# ── Step 5: Generate unique space identifiers ───────────────────────

step "Generating unique space identifiers"

TIMESTAMP="$(date +%Y%m%d%H%M)"
RANDOM_ID="$(head -c 2 /dev/urandom | xxd -p)"
SPACE_NAME="${SPACE_PREFIX}-${TIMESTAMP}-${RANDOM_ID}"
SPACE_KEY="${SPACE_PREFIX}${TIMESTAMP}${RANDOM_ID}"

ok "Space name: $SPACE_NAME"
ok "Space key:  $SPACE_KEY"

# ── Step 6: Create target space (on recovery instance) ───────────────

step "Creating Confluence space: $SPACE_KEY on $RECOVERY_BASE"

HTTP_CODE="$(curl -s -o /tmp/e2e_docker_create_space.json -w "%{http_code}" \
    -X POST "${RECOVERY_BASE}/rest/api/space" \
    -H "Authorization: Bearer ${RECOVERY_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"key\": \"${SPACE_KEY}\", \"name\": \"${SPACE_NAME}\", \"type\": \"global\"}")"

if [[ "$HTTP_CODE" -ne 200 ]]; then
    echo "Response ($HTTP_CODE):"
    cat /tmp/e2e_docker_create_space.json
    fail "Failed to create space (HTTP $HTTP_CODE)"
fi
ok "Space created (HTTP $HTTP_CODE)"

# ── Step 7: Run restore in Docker (to recovery instance) ─────────────

step "Restoring backup to space $SPACE_KEY on $RECOVERY_BASE in Docker"

RESTORE_ARGS="--verbose"
if [[ "$RESOLVE_USERKEYS" == "true" ]]; then
    RESTORE_ARGS="$RESTORE_ARGS --resolve-userkeys"
fi
make docker-restore DIR="$BACKUP_DIR" SPACE="$SPACE_KEY" ENV_FILE="$RECOVERY_ENV_FILE" ARGS="$RESTORE_ARGS"
ok "Restore completed"

# ── Step 8: Summary ─────────────────────────────────────────────────

step "Docker integration test summary"

MANIFEST="${BACKUP_DIR}_restore_manifest.json"
if [[ -f "$MANIFEST" ]]; then
    echo "Restore manifest: $MANIFEST"
    python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
s = m['statistics']
errors = len(m.get('errors', []))
print(f\"  Pages restored:       {s['pages_restored']}\")
print(f\"  Attachments uploaded: {s['attachments_uploaded']}\")
print(f\"  Comments restored:    {s['comments_restored']}\")
print(f\"  Labels restored:      {s['labels_restored']}\")
print(f\"  Users resolved:       {s.get('users_resolved', 0)}\")
print(f\"  Errors:               {errors}\")
if errors:
    for e in m['errors']:
        print(f\"    - [{e['type']}] {e['id']}: {e['error'][:100]}\")
    sys.exit(1)
"
    RESTORE_EXIT=$?
else
    echo "Warning: restore manifest not found at $MANIFEST"
    RESTORE_EXIT=1
fi

echo ""
echo "  Backup source:  $BACKUP_BASE"
echo "  Recovery target: $RECOVERY_BASE"
echo "  Space key:    $SPACE_KEY"
echo "  Space URL:    ${RECOVERY_BASE}/spaces/${SPACE_KEY}/overview"
echo "  Backup dir:   $BACKUP_DIR"

# ── Step 9: Cleanup ──────────────────────────────────────────────────

if [[ "$DELETE_TEST_SPACE" == "true" ]]; then
    step "Deleting test space: $SPACE_KEY"
    DEL_CODE="$(curl -s -o /dev/null -w "%{http_code}" \
        -X DELETE "${RECOVERY_BASE}/rest/api/space/${SPACE_KEY}" \
        -H "Authorization: Bearer ${RECOVERY_TOKEN}")"
    if [[ "$DEL_CODE" -eq 202 || "$DEL_CODE" -eq 204 ]]; then
        ok "Space deleted (HTTP $DEL_CODE)"
    else
        echo "  Warning: failed to delete space (HTTP $DEL_CODE)"
    fi
else
    printf "\n\033[1;33m  Note: test space %s is available for inspection at %s/spaces/%s/overview\033[0m\n" \
        "$SPACE_KEY" "$RECOVERY_BASE" "$SPACE_KEY"
fi

if [[ "$RESTORE_EXIT" -eq 0 ]]; then
    printf "\n\033[1;32mPASSED (Docker)\033[0m\n"
    exit 0
else
    printf "\n\033[1;31mFAILED (Docker - restore had errors)\033[0m\n"
    exit 1
fi

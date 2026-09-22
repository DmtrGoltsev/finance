#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_REF:-}" == 'refs/heads/main' ]]
[[ "${GITHUB_RUN_ID:-}" =~ ^[1-9][0-9]*$ ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
test -n "${GH_TOKEN:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

branch="prod/release-inventory-${GITHUB_RUN_ID}"
ref="refs/heads/${branch}"
workflow='finance-prod-readonly-inventory.yml'
created=no
dispatched=no

cleanup_if_owned() {
  local remote_sha
  remote_sha="$(gh api "repos/${GITHUB_REPOSITORY}/git/ref/heads/${branch}" --jq '.object.sha' 2>/dev/null || true)"
  if [[ "$remote_sha" != "$GITHUB_SHA" ]]; then
    echo "::error::Temporary ref changed or disappeared; refusing cleanup of ${ref}."
    return 1
  fi
  gh api -X DELETE "repos/${GITHUB_REPOSITORY}/git/refs/heads/${branch}" >/dev/null
  created=no
  echo "Removed owned temporary ref ${ref}."
}

on_exit() {
  if [[ "$created" == yes && "$dispatched" == no ]]; then
    cleanup_if_owned || true
  fi
}
trap on_exit EXIT

gh api -X POST "repos/${GITHUB_REPOSITORY}/git/refs" \
  -f ref="$ref" -f sha="$GITHUB_SHA" >/dev/null
created=yes
echo "Created temporary ref ${ref} from main SHA ${GITHUB_SHA}."

gh api -X POST "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/dispatches" \
  -f ref="$branch" \
  -f 'inputs[phase]=inventory' \
  -f "inputs[bootstrap_run_id]=${GITHUB_RUN_ID}" >/dev/null
dispatched=yes

inventory_id=''
for attempt in {1..30}; do
  runs="$(gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs?branch=${branch}&event=workflow_dispatch&per_page=10")"
  inventory_id="$("$PYTHON_BIN" -c '
import json, sys
data = json.load(sys.stdin)
matches = [run for run in data["workflow_runs"]
           if run["head_branch"] == sys.argv[1] and run["head_sha"] == sys.argv[2]]
print(matches[0]["id"] if len(matches) == 1 else "")
' "$branch" "$GITHUB_SHA" <<< "$runs")"
  [[ -n "$inventory_id" ]] && break
  sleep 4
done

if [[ -z "$inventory_id" ]]; then
  echo "::error::Inventory run was not found. Preserve ${ref} for verified teardown."
  exit 1
fi

echo "Inventory run: https://github.com/${GITHUB_REPOSITORY}/actions/runs/${inventory_id}"
for attempt in {1..126}; do
  run="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${inventory_id}")"
  status="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<< "$run")"
  if [[ "$status" == completed ]]; then
    conclusion="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["conclusion"])' <<< "$run")"
    cleanup_if_owned
    if [[ "$conclusion" != success ]]; then
      echo "::error::Inventory concluded ${conclusion}."
      exit 1
    fi
    echo 'Inventory completed and temporary ref removed.'
    exit 0
  fi
  sleep 10
done

echo "::error::Inventory did not complete within the bounded wait. Preserve ${ref} for verified teardown."
exit 1

#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_REF:-}" == 'refs/heads/main' ]]
[[ "${GITHUB_RUN_ID:-}" =~ ^[1-9][0-9]*$ ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" == 1 ]]
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

dispatched=yes
dispatch_response="$(gh api -X POST "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/dispatches" \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  -f ref="$branch" \
  -f 'inputs[phase]=inventory' \
  -f "inputs[bootstrap_run_id]=${GITHUB_RUN_ID}")"
inventory_id="$("$PYTHON_BIN" -c '
import json, sys
def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            sys.exit("duplicate dispatch response field")
        result[key] = value
    return result
response = json.loads(sys.argv[1], object_pairs_hook=unique_object)
if not isinstance(response, dict):
    sys.exit("dispatch response is not an object")
run_id = response.get("workflow_run_id")
if type(run_id) is not int or run_id <= 0:
    sys.exit("dispatch response has no unique workflow_run_id")
print(run_id)
' "$dispatch_response")" || {
  echo "::error::Dispatch did not return one run ID. Preserve ${ref} for verified teardown."
  exit 1
}

echo "Inventory run: https://github.com/${GITHUB_REPOSITORY}/actions/runs/${inventory_id}"
for attempt in {1..126}; do
  run="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${inventory_id}")"
  status="$("$PYTHON_BIN" -c '
import json, sys
run = json.load(sys.stdin)
valid = (run.get("id") == int(sys.argv[1])
         and run.get("event") == "workflow_dispatch"
         and run.get("head_branch") == sys.argv[2]
         and run.get("head_sha") == sys.argv[3]
         and run.get("actor", {}).get("login") == "github-actions[bot]"
         and run.get("display_title") == "finance-inventory-inventory-" + sys.argv[4]
         and run.get("run_attempt") == 1)
if not valid:
    sys.exit("dispatched run metadata mismatch")
print(run["status"])
' "$inventory_id" "$branch" "$GITHUB_SHA" "$GITHUB_RUN_ID" <<< "$run")" || {
    echo "::error::Dispatched run metadata mismatch. Preserve ${ref} for verified teardown."
    exit 1
  }
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

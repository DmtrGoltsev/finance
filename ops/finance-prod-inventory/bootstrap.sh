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
poll_limit="${FINANCE_INVENTORY_POLL_LIMIT:-126}"
poll_interval="${FINANCE_INVENTORY_POLL_INTERVAL_SECONDS:-10}"
[[ "$poll_limit" =~ ^[1-9][0-9]*$ && "$poll_limit" -le 126 ]]
[[ "$poll_interval" =~ ^[0-9]+$ && "$poll_interval" -le 10 ]]
rejected=no
terminal_seen=no
last_issue=''
for ((attempt=1; attempt<=poll_limit; attempt++)); do
  if run="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${inventory_id}" 2>/dev/null)"; then
    if result="$(printf '%s' "$run" | "$PYTHON_BIN" ops/finance-prod-inventory/check_run_metadata.py \
      "$inventory_id" "$branch" "$GITHUB_SHA" "$GITHUB_RUN_ID")"; then
      IFS=$'\t' read -r state field terminal conclusion <<< "$result"
    else
      state=contradictory field=response terminal=unknown conclusion=unknown
    fi
  else
    state=incomplete field=response terminal=unknown conclusion=unknown
  fi

  if [[ "$state" != ready ]]; then
    if [[ "$state:$field" != "$last_issue" ]]; then
      if [[ "$state" == contradictory ]]; then
        echo "::error::Run metadata ${field}: ${state}."
      else
        echo "Run metadata ${field}: ${state}."
      fi
      last_issue="$state:$field"
    fi
    if [[ "$state" == contradictory ]]; then
      rejected=yes
    fi
  else
    last_issue=''
  fi
  if [[ "$terminal" == completed ]]; then
    terminal_seen=yes
  fi
  if [[ "$terminal_seen" == yes && "$rejected" == yes ]]; then
    cleanup_if_owned
    echo '::error::Dispatched run provenance contradicted expected identity.'
    exit 1
  fi
  if [[ "$state" == ready && "$terminal" == completed ]]; then
    cleanup_if_owned
    if [[ "$conclusion" != success ]]; then
      echo "::error::Inventory concluded ${conclusion}."
      exit 1
    fi
    echo 'Inventory completed and temporary ref removed.'
    exit 0
  fi
  if ((attempt < poll_limit)); then
    sleep "$poll_interval"
  fi
done

if [[ "$terminal_seen" == yes ]]; then
  cleanup_if_owned
  echo '::error::Inventory metadata stayed incomplete after terminal run; owned ref removed.'
else
  echo "::error::Inventory did not reach a verified terminal state. Preserve ${ref} for verified teardown."
fi
exit 1

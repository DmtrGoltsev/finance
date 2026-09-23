#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

source_root="${SOURCE_ROOT:?}"
lock_root="$source_root/ops/finance-release/native-n8n"
output="${METRICS_OUT:?}"
feature_sha="${FEATURE_SHA:?}"
[[ "$feature_sha" =~ ^[0-9a-f]{40}$ ]]
test -f "$lock_root/package-lock.json"
test -f "$lock_root/package.json"
test -f "$source_root/ops/finance-n8n/package-lock.json"
test -f "$source_root/apps/backend/pyproject.toml"
test -d "$source_root/ops/finance-n8n/gateway"
test -d "$source_root/apps/backend/src"

root="$(mktemp -d "${RUNNER_TEMP:?}/finance-native-footprint.XXXXXXXX")"
test "$(stat -c %d "$root")" = "$(stat -c %d "$(dirname "$output")")"

df_bytes() { df -B1 --output=avail "$root" | awk 'NR == 2 {print $1}'; }
df_inodes() { df --output=iavail "$root" | awk 'NR == 2 {print $1}'; }
du_bytes() { du -sB1 -- "$1" | awk 'NR == 1 {print $1}'; }

baseline_bytes="$(df_bytes)"
baseline_inodes="$(df_inodes)"
[[ "$baseline_bytes" =~ ^[0-9]+$ && "$baseline_inodes" =~ ^[0-9]+$ ]]
samples="${RUNNER_TEMP}/finance-native-footprint-${GITHUB_RUN_ID:?}.samples"
printf '%s %s\n' "$baseline_bytes" "$baseline_inodes" > "$samples"
(
  while :; do
    available="$(df_bytes)"
    inodes="$(df_inodes)"
    if [[ "$available" =~ ^[0-9]+$ && "$inodes" =~ ^[0-9]+$ ]]; then
      printf '%s %s\n' "$available" "$inodes"
    fi
    sleep 0.2
  done
) >> "$samples" &
sampler_pid=$!
trap 'kill "$sampler_pid" 2>/dev/null || true; wait "$sampler_pid" 2>/dev/null || true' EXIT

mkdir -p "$root/download" "$root/node" "$root/cache" "$root/home" "$root/n8n" "$root/gateway" "$root/worker/backend" "$root/rollback"
export HOME="$root/home"
export XDG_CACHE_HOME="$root/home/.cache"
node_archive=node-v24.21.0-linux-x64.tar.xz
curl --fail --silent --show-error --location --max-time 300 \
  "https://nodejs.org/dist/v24.21.0/${node_archive}" -o "$root/download/$node_archive" >/dev/null 2>&1
curl --fail --silent --show-error --location --max-time 60 \
  https://nodejs.org/dist/v24.21.0/SHASUMS256.txt -o "$root/download/SHASUMS256.txt" >/dev/null 2>&1
expected="$(awk -v name="$node_archive" '$2 == name {print $1}' "$root/download/SHASUMS256.txt")"
[[ "$expected" =~ ^[0-9a-f]{64}$ ]]
printf '%s  %s\n' "$expected" "$root/download/$node_archive" | sha256sum --check --status
tar -xJf "$root/download/$node_archive" -C "$root/node" --strip-components=1
export PATH="$root/node/bin:$PATH"
[[ "$(node --version)" == v24.21.0 ]]
export npm_config_userconfig=/dev/null
export npm_config_update_notifier=false
[[ "$(npm --version)" == 11.19.0 ]]
export npm_config_cache="$root/cache"
export npm_config_registry=https://registry.npmjs.org

cp "$lock_root/package.json" "$lock_root/package-lock.json" "$root/n8n/"
(cd "$root/n8n" && timeout 30m npm ci --omit=dev --no-audit --no-fund >/dev/null 2>&1)
cp "$source_root/ops/finance-n8n/package.json" "$source_root/ops/finance-n8n/package-lock.json" "$root/gateway/"
cp -a "$source_root/ops/finance-n8n/gateway" "$root/gateway/"
(cd "$root/gateway" && timeout 10m npm ci --omit=dev --ignore-scripts --no-audit --no-fund >/dev/null 2>&1)
cp "$source_root/apps/backend/pyproject.toml" "$source_root/apps/backend/README.md" "$root/worker/backend/"
cp -a "$source_root/apps/backend/src" "$root/worker/backend/"
python3.12 -m venv "$root/worker/venv"
PIP_NO_CACHE_DIR=1 PIP_CONFIG_FILE=/dev/null PIP_INDEX_URL=https://pypi.org/simple \
  timeout 15m "$root/worker/venv/bin/python" -m pip install --no-input "$root/worker/backend" >/dev/null 2>&1
worker_dependencies_sha256="$("$root/worker/venv/bin/python" -m pip list --format=freeze | sha256sum | cut -d ' ' -f 1)"

node_stage_bytes="$(du_bytes "$root/node")"
n8n_stage_bytes="$(du_bytes "$root/n8n")"
gateway_stage_bytes="$(du_bytes "$root/gateway")"
worker_stage_bytes="$(du_bytes "$root/worker")"
npm_cache_bytes="$(du_bytes "$root/cache")"
runtime_home_bytes="$(du_bytes "$root/home")"
download_bytes="$(du_bytes "$root/download")"
cp -a "$root/node" "$root/n8n" "$root/gateway" "$root/worker" "$root/rollback/"
rollback_bytes="$(du_bytes "$root/rollback")"
final_stage_bytes="$(du_bytes "$root")"

kill "$sampler_pid" 2>/dev/null || true
wait "$sampler_pid" 2>/dev/null || true
trap - EXIT
read -r min_bytes min_inodes < <(awk 'NR == 1 {b=$1; i=$2} $1 < b {b=$1} $2 < i {i=$2} END {print b, i}' "$samples")
[[ "$min_bytes" =~ ^[0-9]+$ && "$min_inodes" =~ ^[0-9]+$ ]]
(( baseline_bytes >= min_bytes && baseline_inodes >= min_inodes ))

{
  echo 'schema=finance_native_footprint_v1'
  printf 'feature_sha=%s\n' "$feature_sha"
  printf 'n8n_lock_sha256=%s\n' "$(sha256sum "$lock_root/package-lock.json" | cut -d ' ' -f 1)"
  printf 'gateway_lock_sha256=%s\n' "$(sha256sum "$source_root/ops/finance-n8n/package-lock.json" | cut -d ' ' -f 1)"
  printf 'worker_pyproject_sha256=%s\n' "$(sha256sum "$source_root/apps/backend/pyproject.toml" | cut -d ' ' -f 1)"
  printf 'worker_dependencies_sha256=%s\n' "$worker_dependencies_sha256"
  printf 'node_archive_sha256=%s\n' "$expected"
  echo 'node_version=24.21.0'
  echo 'npm_version=11.19.0'
  echo 'sampler_interval_ms=200'
  printf 'baseline_available_bytes=%s\n' "$baseline_bytes"
  printf 'baseline_available_inodes=%s\n' "$baseline_inodes"
  printf 'minimum_sampled_available_bytes=%s\n' "$min_bytes"
  printf 'minimum_sampled_available_inodes=%s\n' "$min_inodes"
  printf 'observed_peak_disk_bytes=%s\n' "$((baseline_bytes - min_bytes))"
  printf 'observed_peak_inodes=%s\n' "$((baseline_inodes - min_inodes))"
  printf 'node_stage_bytes=%s\n' "$node_stage_bytes"
  printf 'n8n_stage_bytes=%s\n' "$n8n_stage_bytes"
  printf 'gateway_stage_bytes=%s\n' "$gateway_stage_bytes"
  printf 'worker_stage_bytes=%s\n' "$worker_stage_bytes"
  printf 'npm_cache_bytes=%s\n' "$npm_cache_bytes"
  printf 'runtime_home_bytes=%s\n' "$runtime_home_bytes"
  printf 'download_bytes=%s\n' "$download_bytes"
  printf 'rollback_copy_bytes=%s\n' "$rollback_bytes"
  printf 'final_stage_bytes=%s\n' "$final_stage_bytes"
} > "$output"

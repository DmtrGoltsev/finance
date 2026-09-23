"""Accept only numeric measurements and fixed public digests."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HASH_FIELDS = (
    "n8n_lock_sha256",
    "gateway_lock_sha256",
    "worker_pyproject_sha256",
    "worker_dependencies_sha256",
    "node_archive_sha256",
)
NUMBER_FIELDS = (
    "baseline_available_bytes",
    "baseline_available_inodes",
    "minimum_sampled_available_bytes",
    "minimum_sampled_available_inodes",
    "observed_peak_disk_bytes",
    "observed_peak_inodes",
    "node_stage_bytes",
    "n8n_stage_bytes",
    "gateway_stage_bytes",
    "worker_stage_bytes",
    "npm_cache_bytes",
    "runtime_home_bytes",
    "download_bytes",
    "rollback_copy_bytes",
    "final_stage_bytes",
)
FIELDS = {
    "schema",
    "feature_sha",
    *HASH_FIELDS,
    "node_version",
    "npm_version",
    "sampler_interval_ms",
    *NUMBER_FIELDS,
}


def parse(data: bytes, expected_sha: str) -> dict[str, str]:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("invalid expected SHA")
    if not data or len(data) > 4096 or b"\r" in data or not data.endswith(b"\n"):
        raise ValueError("invalid evidence")
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("invalid evidence") from exc
    result: dict[str, str] = {}
    for line in lines:
        if line.count("=") != 1:
            raise ValueError("invalid evidence")
        key, value = line.split("=", 1)
        if key not in FIELDS or key in result:
            raise ValueError("invalid evidence")
        result[key] = value
    if result.keys() != FIELDS:
        raise ValueError("invalid evidence")
    if result["schema"] != "finance_native_footprint_v1":
        raise ValueError("invalid evidence")
    if result["feature_sha"] != expected_sha:
        raise ValueError("invalid evidence")
    if result["node_version"] != "24.21.0" or result["npm_version"] != "11.19.0":
        raise ValueError("invalid evidence")
    if result["sampler_interval_ms"] != "200":
        raise ValueError("invalid evidence")
    if any(not re.fullmatch(r"[0-9a-f]{64}", result[name]) for name in HASH_FIELDS):
        raise ValueError("invalid evidence")
    if any(not re.fullmatch(r"[0-9]{1,20}", result[name]) for name in NUMBER_FIELDS):
        raise ValueError("invalid evidence")
    numbers = {name: int(result[name]) for name in NUMBER_FIELDS}
    if numbers["baseline_available_bytes"] - numbers["minimum_sampled_available_bytes"] != numbers["observed_peak_disk_bytes"]:
        raise ValueError("invalid evidence")
    if numbers["baseline_available_inodes"] - numbers["minimum_sampled_available_inodes"] != numbers["observed_peak_inodes"]:
        raise ValueError("invalid evidence")
    return result


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("invalid arguments")
        parse(Path(sys.argv[1]).read_bytes(), sys.argv[2])
    except (OSError, ValueError):
        print("::error::Invalid footprint evidence; no output published.", file=sys.stderr)
        raise SystemExit(1) from None

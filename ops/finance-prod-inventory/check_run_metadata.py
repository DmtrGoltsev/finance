from __future__ import annotations

import json
import sys


CONCLUSIONS = {
    "success", "failure", "cancelled", "timed_out", "skipped",
    "neutral", "action_required", "stale",
}
STATUSES = {"queued", "in_progress", "waiting", "pending", "requested", "completed"}


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def inspect_run(raw: str, run_id: int, branch: str, sha: str, bootstrap_id: str) -> tuple[str, str, str, str]:
    try:
        run = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        return "contradictory", "response", "unknown", "unknown"
    if not isinstance(run, dict):
        return "contradictory", "response", "unknown", "unknown"

    actual_id = run.get("id")
    if actual_id is None:
        return "incomplete", "id", "unknown", "unknown"
    if type(actual_id) is not int or actual_id != run_id:
        return "contradictory", "id", "unknown", "unknown"

    status = run.get("status")
    if status == "completed":
        terminal = "completed"
    elif isinstance(status, str) and status in STATUSES:
        terminal = "active"
    else:
        terminal = "unknown"
    conclusion = run.get("conclusion")
    safe_conclusion = conclusion if isinstance(conclusion, str) and conclusion in CONCLUSIONS else "unknown"
    actor = run.get("actor")
    actor_login = actor.get("login") if isinstance(actor, dict) else actor

    fields = (
        ("event", run.get("event"), "workflow_dispatch"),
        ("head_branch", run.get("head_branch"), branch),
        ("head_sha", run.get("head_sha"), sha),
        ("actor", actor_login, "github-actions[bot]"),
        ("display_title", run.get("display_title"), "finance-inventory-inventory-" + bootstrap_id),
        ("run_attempt", run.get("run_attempt"), 1),
    )
    missing = None
    for field, actual, expected in fields:
        if actual is None or actual == "":
            missing = missing or field
            continue
        if type(actual) is not type(expected) or actual != expected:
            return "contradictory", field, terminal, safe_conclusion

    if status is not None and status != "" and (not isinstance(status, str) or status not in STATUSES):
        return "contradictory", "status", "unknown", "unknown"
    if missing:
        return "incomplete", missing, terminal, safe_conclusion
    if status is None or status == "":
        return "incomplete", "status", "unknown", "unknown"
    if status == "completed" and safe_conclusion == "unknown":
        if conclusion is not None and conclusion != "":
            return "contradictory", "conclusion", "completed", "unknown"
        return "incomplete", "conclusion", "completed", "unknown"
    return "ready", "none", terminal, safe_conclusion


if __name__ == "__main__":
    state = inspect_run(sys.stdin.read(), int(sys.argv[1]), *sys.argv[2:5])
    print("\t".join(state))

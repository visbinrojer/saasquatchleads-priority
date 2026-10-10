import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.scoring import Lead, rank_leads, summarize, thesis_sentence

REPO = Path(__file__).resolve().parents[2]
FILE = REPO / "data" / "runs.json"
MAX_RUNS = 20


def _read_all() -> list[dict]:
    try:
        parsed = json.loads(FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _write_all(runs: list[dict]) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(runs, indent=2), encoding="utf-8")


def _lead_payload(lead: Lead) -> dict:
    return {
        "company": lead.company,
        "domain": lead.domain,
        "industry": lead.industry,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "employees": lead.employees,
        "revenue": lead.revenue,
        "ownership": lead.ownership,
    }


def run_hash(buy_box: dict, leads: list[Lead]) -> str:
    payload = json.dumps({"buyBox": buy_box, "leads": [_lead_payload(lead) for lead in leads]}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_run(buy_box: dict, leads: list[Lead]) -> tuple[dict, bool]:
    digest = run_hash(buy_box, leads)
    existing = _read_all()
    cached = next((run for run in existing if run.get("hash") == digest), None)
    if cached:
        return cached, True

    ranked = rank_leads(leads, buy_box)
    summary = summarize(ranked)
    thesis = thesis_sentence(buy_box)
    run = {
        "id": str(uuid4()),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "hash": digest,
        "buyBox": buy_box,
        "thesis": thesis,
        "summary": {**summary, "thesis": thesis},
        "leads": ranked,
    }
    _write_all([run, *existing][:MAX_RUNS])
    return run, False


def list_runs() -> list[dict]:
    summaries = []
    for run in _read_all():
        summaries.append(
            {
                "id": run["id"],
                "createdAt": run["createdAt"],
                **run["summary"],
                "thesis": run["thesis"],
            }
        )
    return summaries


def get_run(run_id: str) -> dict | None:
    return next((run for run in _read_all() if run["id"] == run_id), None)

from pathlib import Path

from app.csvparse import parse_lead_csv
from app.scoring import DEFAULT_BUY_BOX, parse_money, rank_leads, summarize

CSV = Path(__file__).resolve().parents[2] / "frontend" / "public" / "sample-leads.csv"


def test_parses_revenue_the_way_a_spreadsheet_writes_it():
    assert parse_money("$2.4M") == 2_400_000
    assert parse_money("1,200,000") == 1_200_000
    assert parse_money("800k") == 800_000
    assert parse_money("") is None
    assert parse_money("n/a") is None


def test_sample_scrape_spends_credits_only_on_buy_box_fits():
    scored = rank_leads(parse_lead_csv(CSV.read_text(encoding="utf-8")), DEFAULT_BUY_BOX)
    by_name = {lead["company"]: lead for lead in scored}

    def bucket(name: str) -> str:
        return by_name[name]["bucket"]

    assert bucket("Mesa Air Mechanical") == "enrich"
    assert by_name["Mesa Air Mechanical"]["score"] == 100
    assert bucket("Mesa Air Mechanical (dup)") == "skip"
    assert by_name["Mesa Air Mechanical (dup)"]["duplicateOf"] == "Mesa Air Mechanical"
    assert bucket("Hill Country Plumbing West") == "skip"
    assert bucket("Mister Sparky Local") == "skip"
    assert "Franchise" in by_name["Mister Sparky Local"]["angle"]
    assert "Revenue is missing" in by_name["Oak City HVAC"]["angle"]
    assert bucket("Apex HVAC Partners") == "skip"
    assert bucket("Summit HVAC Holdings") == "skip"
    assert bucket("National Comfort PLC") == "skip"
    assert bucket("Oak City HVAC") == "hold"
    assert by_name["Oak City HVAC"]["score"] >= 72
    assert bucket("Coastal Electric") == "hold"
    assert bucket("BrightSmile Dental") == "skip"
    assert bucket("Lakeside Landscaping") == "skip"
    assert bucket("Brooklyn Boiler Co") == "hold"
    assert bucket("Palmetto HVAC") == "hold"
    assert bucket("No-Name Plumbing") == "skip"
    assert bucket("Bad Domain Electric") == "skip"
    assert bucket("Nearband Climate") == "enrich"
    assert by_name["Nearband Climate"]["warning"] is True
    assert bucket("Savannah Mechanical") == "enrich"
    assert bucket("Low Voltage Atlanta") == "enrich"
    assert bucket("Flagstaff Electric") == "enrich"
    assert bucket("Tiny Ducts") == "skip"
    assert bucket("MegaGrid Electric") == "skip"

    summary = summarize(scored)
    assert summary["total"] == 42
    assert summary["enrich"] < summary["total"] / 2
    assert summary["creditsHeld"] == summary["hold"] + summary["skip"]
    assert summary["enrich"] + summary["hold"] + summary["skip"] == summary["total"]

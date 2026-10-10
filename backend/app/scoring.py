import math
import re
from dataclasses import dataclass

ADJACENT = {
    "hvac": ["mechanical", "refrigeration", "air conditioning"],
    "plumbing": ["piping", "mechanical"],
    "electrical": ["low voltage", "electric"],
}

STATE_NAMES = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}

DEFAULT_BUY_BOX = {
    "industries": ["HVAC", "Plumbing", "Electrical"],
    "states": ["TX", "FL", "AZ", "GA", "NC"],
    "revenueMin": 1_000_000,
    "revenueMax": 8_000_000,
    "employeesMin": 10,
    "employeesMax": 75,
    "excludeFranchise": True,
    "excludePublic": True,
    "excludePe": True,
}


@dataclass
class Lead:
    company: str
    domain: str = ""
    industry: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    employees: int | None = None
    revenue: int | None = None
    ownership: str = ""


def js_round(value: float) -> int:
    return int(math.floor(value + 0.5))


def normalize_text(value: str) -> str:
    text = value.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+ ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_state(value: str) -> str:
    trimmed = value.strip().upper()
    if len(trimmed) == 2:
        return trimmed
    return STATE_NAMES.get(trimmed, trimmed)


def normalize_domain(raw: str) -> str:
    domain = raw.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0].split("?")[0].strip()
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", domain):
        return ""
    return domain


def parse_money(raw: str) -> int | None:
    text = re.sub(r"[$,\s]", "", raw.strip().lower())
    if text in {"", "-", "n/a", "na", "unknown"}:
        return None
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(k|m|b|million|billion|thousand)?", text)
    if not match:
        return None
    value = float(match.group(1))
    if not math.isfinite(value):
        return None
    unit = match.group(2)
    multiplier = {
        "k": 1_000,
        "thousand": 1_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "b": 1_000_000_000,
        "billion": 1_000_000_000,
    }.get(unit or "", 1)
    return js_round(value * multiplier)


def parse_employees(raw: str) -> int | None:
    text = re.sub(r"employees?|,", "", raw.strip().lower()).strip()
    if text in {"", "-", "n/a", "na", "unknown"}:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    value = js_round(float(match.group(1)))
    return value if math.isfinite(value) else None


def ownership_kind(value: str) -> str:
    text = normalize_text(value)
    if not text or text in {"unknown", "n a", "na"}:
        return "unknown"
    if "franchise" in text:
        return "franchise"
    if "public" in text:
        return "public"
    if "pe backed" in text or "private equity" in text or text == "pe" or "sponsor backed" in text:
        return "pe"
    if "independent" in text or "founder" in text or "owner" in text:
        return "independent"
    return "unknown"


def industry_fit(industry: str, wanted: list[str]) -> str:
    if len(wanted) == 0:
        return "open"
    text = normalize_text(industry)
    if not text:
        return "missing"
    for item in wanted:
        target = normalize_text(item)
        if not target:
            continue
        if target in text or text in target:
            return "exact"
    for item in wanted:
        related = ADJACENT.get(normalize_text(item), [])
        if any(entry in text for entry in related):
            return "adjacent"
    return "none"


def band_fit(value: int | None, low_bound: int, high_bound: int) -> str:
    if low_bound <= 0 and high_bound <= 0:
        return "open"
    if value is None:
        return "missing"
    low = min(low_bound, high_bound)
    high = max(low_bound, high_bound)
    if low <= value <= high:
        return "in"
    distance = (low - value) / low if value < low else (value - high) / high
    return "near" if distance <= 0.25 else "far"


def clamp(value: float) -> int:
    return max(0, min(100, js_round(value)))


def location_label(lead: Lead) -> str:
    parts = [part for part in [lead.city, normalize_state(lead.state)] if part]
    return ", ".join(parts) if parts else "an unknown location"


def decision_detail(reasons: list[dict]) -> str:
    negative = sorted((reason for reason in reasons if reason["impact"] < 0), key=lambda reason: reason["impact"])
    if negative:
        return negative[0]["detail"]
    missing = next((reason for reason in reasons if re.search(r"missing", reason["detail"], re.I)), None)
    if missing:
        return missing["detail"]
    if reasons:
        return reasons[0]["detail"]
    return "It does not clear the buy box."


def build_angle(lead: Lead, bucket: str, reasons: list[dict]) -> str:
    place = location_label(lead)
    if bucket == "enrich":
        trade = lead.industry or "the target trade"
        return (
            f"{lead.company} fits the buy box: {trade} in {place}, inside the size band. "
            "Enrich the owner and open with one local fact, succession, or route density."
        )
    headline = decision_detail(reasons)
    if bucket == "hold":
        return f"Hold the credit on {lead.company}. {headline}"
    return f"Skip {lead.company}. {headline}"


def _score_one(lead: Lead, buy_box: dict, index: int) -> dict:
    reasons: list[dict] = []
    points = 0
    warning = False
    forced = None

    def add(label: str, impact: int, detail: str) -> None:
        nonlocal points
        points += impact
        reasons.append({"label": label, "impact": impact, "detail": detail})

    fit = industry_fit(lead.industry, buy_box["industries"])
    if fit == "exact":
        add("Industry", 30, f"{lead.industry} is in the buy box.")
    elif fit == "adjacent":
        add("Industry", 14, f"{lead.industry} is adjacent to the buy box. Worth a look, not a perfect fit.")
    elif fit == "open":
        add("Industry", 8, "No industry constraint on this buy box.")
    elif fit == "missing":
        add("Industry", -10, "Industry is missing, so the thesis cannot be confirmed.")
    else:
        add("Industry", -35, f"{lead.industry or 'This industry'} is outside the buy box.")

    state = normalize_state(lead.state)
    states = [normalize_state(item) for item in buy_box["states"]]
    if len(states) == 0:
        add("Geography", 8, "No geography constraint on this buy box.")
    elif state in states:
        add("Geography", 22, f"{state} is inside the target states.")
    elif not state:
        add("Geography", -16, "State is missing.")
    else:
        add("Geography", -16, f"{state} is outside the target states.")

    revenue_fit = band_fit(lead.revenue, buy_box["revenueMin"], buy_box["revenueMax"])
    if revenue_fit == "in":
        add("Revenue", 22, "Revenue sits inside the band.")
    elif revenue_fit == "near":
        warning = True
        add("Revenue", 8, "Revenue is just outside the band. Check it before you treat this as a core target.")
    elif revenue_fit == "far":
        add("Revenue", -18, "Revenue is well outside the band.")
    elif revenue_fit == "missing":
        add("Revenue", 0, "Revenue is missing. Do not spend a credit until size is confirmed.")
    else:
        add("Revenue", 8, "No revenue constraint on this buy box.")

    employee_fit = band_fit(lead.employees, buy_box["employeesMin"], buy_box["employeesMax"])
    if employee_fit == "in":
        add("Headcount", 16, "Headcount sits inside the band.")
    elif employee_fit == "near":
        warning = True
        add("Headcount", 6, "Headcount is just outside the band.")
    elif employee_fit == "far":
        add("Headcount", -18, "Headcount is well outside the band.")
    elif employee_fit == "missing":
        add("Headcount", 0, "Headcount is missing. Revenue and trade still carry the score.")
    else:
        add("Headcount", 6, "No headcount constraint on this buy box.")

    domain = normalize_domain(lead.domain)
    if not domain:
        forced = "skip"
        add("Identity", -25, "No usable domain. There is nothing reliable to enrich.")
    else:
        add("Identity", 10, f"{domain} can be enriched.")

    ownership = ownership_kind(lead.ownership)
    if ownership == "franchise" and buy_box["excludeFranchise"]:
        forced = "skip"
        add("Ownership", -40, "Franchise. Excluded from this buy box.")
    elif ownership == "public" and buy_box["excludePublic"]:
        forced = "skip"
        add("Ownership", -40, "Public company. Excluded from this buy box.")
    elif ownership == "pe" and buy_box["excludePe"]:
        forced = "skip"
        add("Ownership", -40, "PE-backed. Excluded from this buy box.")
    elif ownership == "independent":
        add("Ownership", 0, "Ownership looks independent.")
    else:
        add("Ownership", 0, "Ownership was not provided.")

    score = clamp(points)
    if forced == "skip":
        bucket = "skip"
        score = min(score, 24)
    elif revenue_fit == "missing":
        bucket = "hold" if score >= 45 else "skip"
        if score >= 72:
            warning = True
    elif score >= 72:
        bucket = "enrich"
    elif score >= 45:
        bucket = "hold"
    else:
        bucket = "skip"

    scored_lead = Lead(
        company=lead.company,
        domain=domain,
        industry=lead.industry,
        city=lead.city,
        state=state,
        country=lead.country,
        employees=lead.employees,
        revenue=lead.revenue,
        ownership=lead.ownership,
    )
    return {
        "company": scored_lead.company,
        "domain": domain,
        "industry": scored_lead.industry,
        "city": scored_lead.city,
        "state": state,
        "country": scored_lead.country,
        "employees": scored_lead.employees,
        "revenue": scored_lead.revenue,
        "ownership": scored_lead.ownership,
        "id": f"{domain or 'row'}-{index}",
        "score": score,
        "bucket": bucket,
        "reasons": reasons,
        "warning": warning,
        "angle": build_angle(scored_lead, bucket, reasons),
    }


def rank_leads(leads: list[Lead], buy_box: dict) -> list[dict]:
    scored = [_score_one(lead, buy_box, index) for index, lead in enumerate(leads)]
    best_by_domain: dict[str, int] = {}
    for index, lead in enumerate(scored):
        if not lead["domain"]:
            continue
        current = best_by_domain.get(lead["domain"])
        if current is None or lead["score"] > scored[current]["score"]:
            best_by_domain[lead["domain"]] = index

    ranked = []
    for index, lead in enumerate(scored):
        if not lead["domain"]:
            ranked.append(lead)
            continue
        best = best_by_domain.get(lead["domain"])
        if best is None or best == index:
            ranked.append(lead)
            continue
        canonical = scored[best]
        detail = f"Same domain as {canonical['company']}. Keep a single record."
        ranked.append(
            {
                **lead,
                "score": 0,
                "bucket": "skip",
                "warning": False,
                "duplicateOf": canonical["company"],
                "reasons": [{"label": "Duplicate", "impact": 0, "detail": detail}],
                "angle": f"Skip {lead['company']}. {detail}",
            }
        )
    return ranked


def summarize(leads: list[dict]) -> dict:
    enrich = sum(1 for lead in leads if lead["bucket"] == "enrich")
    hold = sum(1 for lead in leads if lead["bucket"] == "hold")
    skip = sum(1 for lead in leads if lead["bucket"] == "skip")
    return {"total": len(leads), "enrich": enrich, "hold": hold, "skip": skip, "creditsHeld": hold + skip}


def format_compact(value: int) -> str:
    if value >= 1_000_000_000:
        return f"${_trim(value / 1_000_000_000)}B"
    if value >= 1_000_000:
        return f"${_trim(value / 1_000_000)}M"
    if value >= 1_000:
        return f"${_trim(value / 1_000)}k"
    return f"${round(value)}"


def _trim(value: float) -> str:
    fixed = f"{value:.0f}" if value >= 10 else f"{value:.1f}"
    return fixed.replace(".0", "")


def thesis_sentence(buy_box: dict) -> str:
    trades = ", ".join(buy_box["industries"]) if buy_box["industries"] else "any trade"
    states = ", ".join(buy_box["states"]) if buy_box["states"] else "any state"
    if buy_box["revenueMin"] > 0 or buy_box["revenueMax"] > 0:
        revenue = f"{format_compact(buy_box['revenueMin'])}–{format_compact(buy_box['revenueMax'])} revenue"
    else:
        revenue = "any revenue"
    if buy_box["employeesMin"] > 0 or buy_box["employeesMax"] > 0:
        people = f"{buy_box['employeesMin']}–{buy_box['employeesMax']} people"
    else:
        people = "any headcount"
    return f"{trades} in {states}, {revenue}, {people}."

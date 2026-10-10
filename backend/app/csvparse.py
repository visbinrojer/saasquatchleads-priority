import re

from app.scoring import Lead, normalize_domain, parse_employees, parse_money

HEADER_MAP = {
    "company": "company",
    "name": "company",
    "company_name": "company",
    "companyname": "company",
    "domain": "domain",
    "website": "domain",
    "url": "domain",
    "web": "domain",
    "industry": "industry",
    "category": "industry",
    "vertical": "industry",
    "city": "city",
    "state": "state",
    "region": "state",
    "country": "country",
    "employees": "employees",
    "employee_count": "employees",
    "employeecount": "employees",
    "headcount": "employees",
    "revenue": "revenue",
    "revenue_estimate": "revenue",
    "annual_revenue": "revenue",
    "estimated_revenue": "revenue",
    "ownership": "ownership",
    "owner_type": "ownership",
    "ownertype": "ownership",
}


def parse_csv_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    row: list[str] = []
    cell = ""
    in_quotes = False
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if in_quotes:
            if char == '"' and nxt == '"':
                cell += '"'
                index += 2
                continue
            if char == '"':
                in_quotes = False
            else:
                cell += char
            index += 1
            continue
        if char == '"':
            in_quotes = True
        elif char == ",":
            row.append(cell)
            cell = ""
        elif char == "\n":
            row.append(cell)
            rows.append(row)
            row = []
            cell = ""
        elif char != "\r":
            cell += char
        index += 1
    if cell or row:
        row.append(cell)
        rows.append(row)
    return [cells for cells in rows if any(value.strip() for value in cells)]


def parse_lead_csv(text: str) -> list[Lead]:
    rows = parse_csv_rows(text)
    if len(rows) < 2:
        return []
    headers = [re.sub(r"\s+", "_", header.strip().lower()) for header in rows[0]]
    leads: list[Lead] = []
    for cells in rows[1:]:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            key = HEADER_MAP.get(header)
            if key:
                record[key] = cells[index].strip() if index < len(cells) else ""
        company = record.get("company", "").strip()
        if not company:
            continue
        leads.append(
            Lead(
                company=company,
                domain=normalize_domain(record.get("domain", "")),
                industry=record.get("industry", "").strip(),
                city=record.get("city", "").strip(),
                state=record.get("state", "").strip().upper(),
                country=record.get("country", "").strip(),
                employees=parse_employees(record.get("employees", "")),
                revenue=parse_money(record.get("revenue", "")),
                ownership=record.get("ownership", "").strip(),
            )
        )
    return leads

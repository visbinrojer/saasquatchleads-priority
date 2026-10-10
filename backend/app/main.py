from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.csvparse import parse_lead_csv
from app.scoring import Lead, rank_leads, summarize, thesis_sentence
from app.store import get_run, list_runs, save_run

app = FastAPI(title="Priority", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BuyBoxIn(BaseModel):
    industries: list[str] = []
    states: list[str] = []
    revenueMin: int = 0
    revenueMax: int = 0
    employeesMin: int = 0
    employeesMax: int = 0
    excludeFranchise: bool = True
    excludePublic: bool = True
    excludePe: bool = True


class LeadIn(BaseModel):
    company: str
    domain: str = ""
    industry: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    employees: int | None = None
    revenue: int | None = None
    ownership: str = ""


class ScoreRequest(BaseModel):
    buyBox: BuyBoxIn
    leads: list[LeadIn] = Field(default_factory=list)


class ParseRequest(BaseModel):
    csv: str


def _buy_box(model: BuyBoxIn) -> dict:
    return model.model_dump()


def _leads(models: list[LeadIn]) -> list[Lead]:
    return [Lead(**model.model_dump()) for model in models]


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/parse")
def parse_csv(body: ParseRequest):
    leads = parse_lead_csv(body.csv)
    return {"leads": [lead.__dict__ for lead in leads]}


@app.post("/api/score")
def score(body: ScoreRequest):
    if len(body.leads) > 5000:
        raise HTTPException(status_code=400, detail="Rank up to 5,000 companies at a time.")
    buy_box = _buy_box(body.buyBox)
    ranked = rank_leads(_leads(body.leads), buy_box)
    return {"leads": ranked, "summary": summarize(ranked), "thesis": thesis_sentence(buy_box)}


@app.get("/api/runs")
def runs():
    return {"runs": list_runs()}


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    found = get_run(run_id)
    if not found:
        raise HTTPException(status_code=404, detail="Ranking not found.")
    return {"run": found}


@app.post("/api/runs")
def create_run(body: ScoreRequest):
    if len(body.leads) == 0:
        raise HTTPException(status_code=400, detail="Upload at least one company.")
    if len(body.leads) > 5000:
        raise HTTPException(status_code=400, detail="Rank up to 5,000 companies per save.")
    run_record, cached = save_run(_buy_box(body.buyBox), _leads(body.leads))
    return {
        "cached": cached,
        "id": run_record["id"],
        "createdAt": run_record["createdAt"],
        "summary": run_record["summary"],
        "thesis": run_record["thesis"],
    }

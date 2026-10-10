# Priority

Rank a scraped company list against an acquisition buy box before spending an enrichment credit.

SaaSquatch already scrapes companies and unlocks a full contact profile with one credit. Priority sits in front of that unlock. A searcher states a buy box, uploads the CSV they already have, and gets three buckets:

- **Enrich now** — independent, in the trade, in the states, inside the size band, and identifiable by domain.
- **Hold** — close, but missing revenue or a near-miss should be checked before a credit is spent.
- **Skip** — wrong trade, franchise, public, PE-backed, duplicate domain, or no domain.

Each row shows the points behind the score. Export is a filtered CSV that drops back into the tool they already use.

The sample file is fictional. It is shaped like a SaaSquatch export so the demo runs with no login and no live scrape.

## Setup

Requires Python 3.12+ and Node.js 22+.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r backend/requirements.txt
npm install
npm install --prefix frontend
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
npm install
npm install --prefix frontend
```

## Run

```bash
npm test
npm run dev
```

| Surface | URL |
| --- | --- |
| React app | http://localhost:5173 |
| FastAPI | http://127.0.0.1:8000 |
| OpenAPI docs | http://127.0.0.1:8000/docs |

`npm test` checks the sample list: a perfect fit scores 100, missing revenue stays on hold even with a high score, franchises and PE-backed names are skipped, and a repeated domain keeps a single record.

The app loads `frontend/public/sample-leads.csv` on its own (42 companies). Upload replaces it. Expected columns, with common aliases accepted:

`company, domain, industry, city, state, country, employees, revenue, ownership`

Revenue accepts `3200000`, `$3.2M`, and `800k`.

## Demo notebook

`notebooks/priority_demo.ipynb` calls `POST /api/parse`, `POST /api/score`, and `POST /api/runs`. The saved outputs are already in the file.

On the default buy box (HVAC, plumbing, and electrical in TX, FL, AZ, GA, NC, $1–8M, 10–75 people) the result is **20 enrich, 6 hold, 16 skip**. A dental buy box drops that to **1 enrich**.

```bash
pip install jupyter
jupyter notebook notebooks/priority_demo.ipynb
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/parse` | Turn CSV text into company rows |
| POST | `/api/score` | Rank rows against a buy box |
| GET | `/api/runs` | List saved rankings |
| GET | `/api/runs/{id}` | Load one ranking |
| POST | `/api/runs` | Save a ranking, or return the existing one when the input hash matches |

The browser does not score leads. Vite proxies `/api` to FastAPI.

## Stack

| Layer | Choice |
| --- | --- |
| UI | React 19, Vite |
| API | FastAPI, Pydantic, Uvicorn |
| Scoring | `backend/app/scoring.py` |
| Local store | `data/runs.json`, gitignored. Same buy box and list are not written twice. |
| Production database | Postgres. Schema in `db/schema.sql`. `companies.domain` is unique. |
| Cache | SHA-256 of the buy box plus rows. Postgres unique index on `score_runs.input_hash`. At higher volume, that key sits in Redis for 24 hours in front of Postgres. |
| Hosting | React as a static build. FastAPI as a short-lived request, not an always-on crawler. |

## Layout

```
frontend/                          React app
backend/app/                       FastAPI, scoring, CSV parse, JSON store
backend/tests/                     pytest
frontend/public/sample-leads.csv   fictional dataset
notebooks/priority_demo.ipynb      API walkthrough
db/schema.sql                      Postgres target
```

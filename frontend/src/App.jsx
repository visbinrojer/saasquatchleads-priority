import { useEffect, useMemo, useRef, useState } from "react";
import { getRun, listRuns, parseCsv, saveRun, scoreLeads } from "./api.js";

const DEFAULT_DRAFT = {
  industries: "HVAC, Plumbing, Electrical",
  states: "TX, FL, AZ, GA, NC",
  revenueMin: "1",
  revenueMax: "8",
  employeesMin: "10",
  employeesMax: "75",
  excludeFranchise: true,
  excludePublic: true,
  excludePe: true,
};

const BUCKET_LABEL = { enrich: "Enrich now", hold: "Hold", skip: "Skip" };

function splitList(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function draftToBuyBox(draft) {
  const millions = (value) => {
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount <= 0) return 0;
    return Math.round(amount * 1_000_000);
  };
  const people = (value) => {
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount <= 0) return 0;
    return Math.round(amount);
  };
  return {
    industries: splitList(draft.industries),
    states: splitList(draft.states).map((state) => state.toUpperCase()),
    revenueMin: millions(draft.revenueMin),
    revenueMax: millions(draft.revenueMax),
    employeesMin: people(draft.employeesMin),
    employeesMax: people(draft.employeesMax),
    excludeFranchise: draft.excludeFranchise,
    excludePublic: draft.excludePublic,
    excludePe: draft.excludePe,
  };
}

function buyBoxToDraft(buyBox) {
  return {
    industries: buyBox.industries.join(", "),
    states: buyBox.states.join(", "),
    revenueMin: buyBox.revenueMin ? String(buyBox.revenueMin / 1_000_000) : "",
    revenueMax: buyBox.revenueMax ? String(buyBox.revenueMax / 1_000_000) : "",
    employeesMin: buyBox.employeesMin ? String(buyBox.employeesMin) : "",
    employeesMax: buyBox.employeesMax ? String(buyBox.employeesMax) : "",
    excludeFranchise: buyBox.excludeFranchise,
    excludePublic: buyBox.excludePublic,
    excludePe: buyBox.excludePe,
  };
}

function toLead(lead) {
  return {
    company: lead.company,
    domain: lead.domain,
    industry: lead.industry,
    city: lead.city,
    state: lead.state,
    country: lead.country,
    employees: lead.employees,
    revenue: lead.revenue,
    ownership: lead.ownership,
  };
}

function formatRevenue(value) {
  if (value == null) return "—";
  if (value >= 1_000_000) {
    const millions = value / 1_000_000;
    const text = millions >= 10 ? millions.toFixed(0) : millions.toFixed(1).replace(/\.0$/, "");
    return `$${text}M`;
  }
  if (value >= 1000) return `$${Math.round(value / 1000)}k`;
  return `$${value}`;
}

function compareLeads(a, b, key, asc) {
  const direction = asc ? 1 : -1;
  if (key === "company") return a.company.localeCompare(b.company) * direction;
  if (key === "revenue") return ((a.revenue ?? -1) - (b.revenue ?? -1)) * direction;
  if (key === "employees") return ((a.employees ?? -1) - (b.employees ?? -1)) * direction;
  return (a.score - b.score) * direction || a.company.localeCompare(b.company);
}

function leadsToCsv(leads) {
  const headers = ["bucket", "score", "company", "domain", "industry", "city", "state", "country", "employees", "revenue", "ownership", "reasons", "angle"];
  const lines = [headers.join(",")];
  for (const lead of leads) {
    const values = [
      lead.bucket ?? "",
      lead.score ?? "",
      lead.company,
      lead.domain,
      lead.industry,
      lead.city,
      lead.state,
      lead.country,
      lead.employees ?? "",
      lead.revenue ?? "",
      lead.ownership,
      (lead.reasons ?? []).map((reason) => reason.detail).join(" | "),
      lead.angle ?? "",
    ].map((value) => {
      const text = String(value);
      return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
    });
    lines.push(values.join(","));
  }
  return lines.join("\n");
}

export default function App() {
  const [draft, setDraft] = useState(DEFAULT_DRAFT);
  const [leads, setLeads] = useState([]);
  const [ranked, setRanked] = useState([]);
  const [summary, setSummary] = useState({ total: 0, enrich: 0, hold: 0, skip: 0, creditsHeld: 0 });
  const [thesis, setThesis] = useState("Set a buy box and load a company list.");
  const [sourceLabel, setSourceLabel] = useState("No list loaded");
  const [usingSample, setUsingSample] = useState(false);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("score");
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [runs, setRuns] = useState([]);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const fileRef = useRef(null);
  const requestId = useRef(0);
  const buyBox = useMemo(() => draftToBuyBox(draft), [draft]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = ranked.filter((lead) => {
      if (filter !== "all" && lead.bucket !== filter) return false;
      if (!needle) return true;
      return [lead.company, lead.domain, lead.industry, lead.city, lead.state].join(" ").toLowerCase().includes(needle);
    });
    rows.sort((a, b) => compareLeads(a, b, sortKey, sortAsc));
    return rows;
  }, [ranked, filter, query, sortKey, sortAsc]);

  const selected = ranked.find((lead) => lead.id === selectedId) ?? null;

  useEffect(() => {
    loadSample();
    refreshRuns();
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (leads.length === 0) return undefined;
    const id = requestId.current + 1;
    requestId.current = id;
    const timer = setTimeout(async () => {
      try {
        const result = await scoreLeads(buyBox, leads);
        if (id !== requestId.current) return;
        setRanked(result.leads);
        setSummary(result.summary);
        setThesis(result.thesis);
        setLoadError("");
      } catch (error) {
        if (id !== requestId.current) return;
        setLoadError(error.message || "The API did not respond. Start FastAPI on port 8000.");
      }
    }, 120);
    return () => clearTimeout(timer);
  }, [leads, buyBox]);

  async function refreshRuns() {
    try {
      const body = await listRuns();
      setRuns(body.runs);
    } catch {
      setRuns([]);
    }
  }

  async function loadSample() {
    setLoadError("");
    const response = await fetch("/sample-leads.csv");
    if (!response.ok) {
      setLoadError("Sample list failed to load.");
      return;
    }
    await applyCsv(await response.text(), "Sample scrape", true);
  }

  async function applyCsv(csv, label, sample) {
    try {
      const parsed = await parseCsv(csv);
      if (parsed.leads.length === 0) {
        setLoadError("No companies found. Use a header row with company, domain, industry, city, state, employees, revenue, ownership.");
        return;
      }
      setLeads(parsed.leads);
      setUsingSample(sample);
      setSourceLabel(`${label} · ${parsed.leads.length} companies`);
      setSelectedId(null);
      setFilter("all");
      setStatus("");
      setLoadError("");
    } catch (error) {
      setLoadError(error.message || "Could not parse that file.");
    }
  }

  function onUpload(file) {
    const reader = new FileReader();
    reader.onload = () => applyCsv(String(reader.result ?? ""), file.name, false);
    reader.readAsText(file);
  }

  async function saveRanking() {
    setSaving(true);
    setStatus("");
    try {
      const body = await saveRun(buyBox, leads);
      setStatus(body.cached ? `Already saved · ${body.id.slice(0, 8)}` : `Saved · ${body.id.slice(0, 8)}`);
      await refreshRuns();
    } catch (error) {
      setStatus(error.message || "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function openRun(id) {
    const body = await getRun(id);
    setDraft(buyBoxToDraft(body.run.buyBox));
    setLeads(body.run.leads.map(toLead));
    setUsingSample(false);
    setSourceLabel(`Saved ranking · ${body.run.leads.length} companies`);
    setSelectedId(null);
    setStatus(`Loaded ${id.slice(0, 8)}`);
  }

  function exportVisible() {
    const blob = new Blob([leadsToCsv(visible)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `priority-${filter}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function toggleSort(key) {
    if (sortKey === key) setSortAsc((value) => !value);
    else {
      setSortKey(key);
      setSortAsc(key === "company");
    }
  }

  return (
    <div className="shell">
      <header className="top">
        <div className="top-row">
          <div>
            <p className="kicker">Priority</p>
            <h1>Which scraped companies deserve a credit</h1>
            <p className="thesis">{thesis}</p>
          </div>
          <div>
            <p className="source">{sourceLabel}</p>
            <button type="button" className="primary" onClick={saveRanking} disabled={saving || leads.length === 0}>
              {saving ? "Saving" : "Save ranking"}
            </button>
          </div>
        </div>
        {status ? <p className="status">{status}</p> : null}
      </header>

      <div className="layout">
        <aside className="side">
          <label className="field">
            <span>Trades <em className="hint">Comma-separated</em></span>
            <input aria-label="Trades" value={draft.industries} onChange={(event) => setDraft({ ...draft, industries: event.target.value })} />
          </label>
          <label className="field">
            <span>States <em className="hint">Comma-separated</em></span>
            <input aria-label="States" value={draft.states} onChange={(event) => setDraft({ ...draft, states: event.target.value })} />
          </label>
          <div className="pair">
            <label className="field">
              <span>Revenue min <em className="hint">$ millions</em></span>
              <input aria-label="Minimum revenue in millions" inputMode="decimal" value={draft.revenueMin} onChange={(event) => setDraft({ ...draft, revenueMin: event.target.value })} />
            </label>
            <label className="field">
              <span>Revenue max <em className="hint">$ millions</em></span>
              <input aria-label="Maximum revenue in millions" inputMode="decimal" value={draft.revenueMax} onChange={(event) => setDraft({ ...draft, revenueMax: event.target.value })} />
            </label>
            <label className="field">
              <span>People min</span>
              <input aria-label="Minimum employees" inputMode="numeric" value={draft.employeesMin} onChange={(event) => setDraft({ ...draft, employeesMin: event.target.value })} />
            </label>
            <label className="field">
              <span>People max</span>
              <input aria-label="Maximum employees" inputMode="numeric" value={draft.employeesMax} onChange={(event) => setDraft({ ...draft, employeesMax: event.target.value })} />
            </label>
          </div>
          <p className="legend">Exclude</p>
          <label className="check"><input type="checkbox" checked={draft.excludeFranchise} onChange={(event) => setDraft({ ...draft, excludeFranchise: event.target.checked })} /> Franchises</label>
          <label className="check"><input type="checkbox" checked={draft.excludePublic} onChange={(event) => setDraft({ ...draft, excludePublic: event.target.checked })} /> Public companies</label>
          <label className="check"><input type="checkbox" checked={draft.excludePe} onChange={(event) => setDraft({ ...draft, excludePe: event.target.checked })} /> PE-backed</label>
          <div className="actions">
            <button type="button" className="btn" onClick={loadSample}>Load sample</button>
            <button type="button" className="btn" onClick={() => fileRef.current?.click()}>Upload CSV</button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ""; }} />
          </div>
          <p><a className="link" href="/sample-leads.csv">Download the column template</a></p>
          {loadError ? <p className="error">{loadError}</p> : null}

          {runs.length > 0 ? (
            <div>
              <h2 className="section-label">Saved rankings</h2>
              <ul className="runs">
                {runs.map((run) => (
                  <li key={run.id}>
                    <button type="button" className="run" onClick={() => openRun(run.id)}>
                      <strong>{run.enrich} enrich / {run.total}</strong>
                      <span className="domain">{new Date(run.createdAt).toLocaleString()} · {run.thesis}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>

        <section className="main">
          <div className="stats">
            <div className="stat"><span className="section-label">In the list</span><b>{summary.total}</b></div>
            <div className="stat"><span className="section-label">Enrich now</span><b className="enrich">{summary.enrich}</b></div>
            <div className="stat"><span className="section-label">Hold</span><b className="hold">{summary.hold}</b></div>
            <div className="stat"><span className="section-label">Credits held back</span><b className="skip">{summary.creditsHeld}</b></div>
          </div>
          {usingSample ? (
            <p className="banner">Sample companies are fictional and stand in for a SaaSquatch export. Upload your own CSV when you have one. Same columns, same ranking.</p>
          ) : null}
          <div className="toolbar">
            {["all", "enrich", "hold", "skip"].map((key) => (
              <button key={key} type="button" className={filter === key ? "chip on" : "chip"} onClick={() => setFilter(key)}>
                {key === "all" ? "All" : BUCKET_LABEL[key]} {key === "all" ? summary.total : summary[key]}
              </button>
            ))}
            <input className="search" aria-label="Search companies" placeholder="Search company, trade, city" value={query} onChange={(event) => setQuery(event.target.value)} />
            <button type="button" className="btn" onClick={exportVisible} disabled={visible.length === 0}>Export {visible.length}</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th><button type="button" className="text-btn" onClick={() => toggleSort("score")}>Score {sortKey === "score" ? (sortAsc ? "↑" : "↓") : ""}</button></th>
                  <th><button type="button" className="text-btn" onClick={() => toggleSort("company")}>Company {sortKey === "company" ? (sortAsc ? "↑" : "↓") : ""}</button></th>
                  <th>Trade</th>
                  <th>Where</th>
                  <th><button type="button" className="text-btn" onClick={() => toggleSort("revenue")}>Revenue {sortKey === "revenue" ? (sortAsc ? "↑" : "↓") : ""}</button></th>
                  <th><button type="button" className="text-btn" onClick={() => toggleSort("employees")}>People {sortKey === "employees" ? (sortAsc ? "↑" : "↓") : ""}</button></th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((lead) => (
                  <tr key={lead.id} className={selectedId === lead.id ? "selected" : ""} onClick={() => setSelectedId(lead.id)}>
                    <td>
                      <div className="num"><strong>{lead.score}</strong></div>
                      <div className="bar"><i style={{ width: `${lead.score}%` }} /></div>
                    </td>
                    <td>
                      <button type="button" className="company" onClick={() => setSelectedId(lead.id)}>{lead.company}</button>
                      <div className="domain">{lead.domain || "No domain"}</div>
                    </td>
                    <td className="quiet">{lead.industry || "—"}</td>
                    <td className="quiet">{[lead.city, lead.state].filter(Boolean).join(", ") || "—"}</td>
                    <td className="num">{formatRevenue(lead.revenue)}</td>
                    <td className="num">{lead.employees ?? "—"}</td>
                    <td><span className={`badge ${lead.bucket}`}>{BUCKET_LABEL[lead.bucket]}{lead.warning ? " *" : ""}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {visible.length === 0 ? <p className="empty">Nothing in this view. Change the filter or upload a list.</p> : null}
          </div>
        </section>
      </div>

      {selected ? (
        <div className="backdrop" onClick={() => setSelectedId(null)}>
          <aside className="drawer" role="dialog" aria-label={`${selected.company} ranking`} onClick={(event) => event.stopPropagation()}>
            <div className="top-row">
              <div>
                <span className={`badge ${selected.bucket}`}>{BUCKET_LABEL[selected.bucket]} · {selected.score}</span>
                <h2>{selected.company}</h2>
                <p className="quiet">{[selected.industry, selected.city, selected.state, selected.domain].filter(Boolean).join(" · ")}</p>
              </div>
              <button type="button" className="text-btn" onClick={() => setSelectedId(null)}>Close</button>
            </div>
            <p>{selected.angle}</p>
            <button type="button" className="text-btn" onClick={() => navigator.clipboard.writeText(selected.angle)}>Copy note</button>
            <h3 className="section-label">Why this score</h3>
            <ul className="reasons">
              {selected.reasons.map((reason) => (
                <li key={reason.label}>
                  <span><strong>{reason.label}. </strong><span className="quiet">{reason.detail}</span></span>
                  <strong className={reason.impact < 0 ? "skip" : "enrich"}>{reason.impact > 0 ? `+${reason.impact}` : reason.impact}</strong>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

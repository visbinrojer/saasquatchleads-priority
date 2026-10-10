async function request(path, options) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || "Request failed.");
  }
  return body;
}

export function parseCsv(csv) {
  return request("/api/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csv }),
  });
}

export function scoreLeads(buyBox, leads) {
  return request("/api/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buyBox, leads }),
  });
}

export function saveRun(buyBox, leads) {
  return request("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buyBox, leads }),
  });
}

export function listRuns() {
  return request("/api/runs");
}

export function getRun(id) {
  return request(`/api/runs/${id}`);
}

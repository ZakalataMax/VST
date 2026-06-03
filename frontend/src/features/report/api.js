const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function parseResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const message = payload?.detail || "Request failed.";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return payload;
}

export async function fetchCsvDays() {
  const response = await fetch(`${API_BASE_URL}/api/csv/days`);
  return parseResponse(response);
}

export function summarizeCsvDays(days) {
  const list = days || [];
  if (!list.length) {
    return { rowCount: 0, minDate: null, maxDate: null };
  }
  const sorted = [...list].sort((left, right) => left.date.localeCompare(right.date));
  return {
    rowCount: list.reduce((sum, day) => sum + (day.rowCount || 0), 0),
    minDate: sorted[0].date,
    maxDate: sorted[sorted.length - 1].date,
  };
}

export async function fetchReportTemplate() {
  const response = await fetch(`${API_BASE_URL}/api/report/template`);
  return parseResponse(response);
}

export async function runReport(body) {
  const response = await fetch(`${API_BASE_URL}/api/report/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

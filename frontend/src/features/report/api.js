const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

export async function fetchDbDays() {
  const response = await fetch(`${API_BASE_URL}/api/db/days`);
  return parseResponse(response);
}

export async function fetchDbStatus() {
  const response = await fetch(`${API_BASE_URL}/api/db/status`);
  return parseResponse(response);
}

export async function importCsvFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/db/import`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function importCsvText(csvText, fileName = "import.csv") {
  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
  const file = new File([blob], fileName, { type: "text/csv" });
  return importCsvFile(file);
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const UPLOAD_API_BASE_URL = import.meta.env.VITE_API_DIRECT_URL || API_BASE_URL;

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

export async function uploadLogs(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${UPLOAD_API_BASE_URL}/api/logs/upload`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function fetchLogDays() {
  const response = await fetch(`${API_BASE_URL}/api/logs/days`);
  return parseResponse(response);
}

export async function fetchLogFiles(date) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  const response = await fetch(`${API_BASE_URL}/api/logs/files${query}`);
  return parseResponse(response);
}

export async function runMerchantWindowTest(fileIds, options = {}) {
  const response = await fetch(`${API_BASE_URL}/api/logs/merchant-window-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_ids: fileIds,
      date: options.date || null,
      timeFrom: options.timeFrom || "11:00:00",
      timeTo: options.timeTo || "15:00:00",
      minAttempts: options.minAttempts ?? 2,
    }),
  });
  return parseResponse(response);
}

export async function parseStoredLogs(fileIds) {
  const response = await fetch(`${API_BASE_URL}/api/logs/parse/stored`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_ids: fileIds }),
  });
  return parseResponse(response);
}

export async function parseLogs(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${API_BASE_URL}/api/logs/parse`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function deleteLogFile(fileId) {
  const response = await fetch(`${API_BASE_URL}/api/logs/files/${fileId}`, {
    method: "DELETE",
  });
  return parseResponse(response);
}

export function rowsToCsv(columns, rows) {
  const escape = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const header = columns.map(escape).join(",");
  const body = rows.map((row) => columns.map((col) => escape(row[col])).join(",")).join("\n");
  return `${header}\n${body}`;
}

export function downloadResultsCsv(columns, rows, fileName = "report-results.csv") {
  const blob = new Blob([rowsToCsv(columns, rows)], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

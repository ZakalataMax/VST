import { getTrimmedLines } from "./formatter";

export const analyzeDuplicates = (value) => {
  const lines = getTrimmedLines(value);
  const seen = new Set();
  const duplicateValues = new Set();
  const counts = new Map();
  const numbers = [];
  const invalid = [];

  for (const line of lines) {
    const parsed = Number.parseInt(line, 10);

    if (Number.isNaN(parsed)) {
      invalid.push(line);
      continue;
    }

    if (seen.has(parsed)) {
      duplicateValues.add(parsed);
    } else {
      seen.add(parsed);
    }
    counts.set(parsed, (counts.get(parsed) ?? 0) + 1);

    numbers.push(parsed);
  }

  const duplicates = Array.from(duplicateValues).sort((a, b) => a - b);

  return {
    total: numbers.length,
    unique: seen.size,
    duplicateCount: duplicateValues.size,
    duplicates,
    duplicateOccurrences: Object.fromEntries(
      duplicates.map((valueNumber) => [valueNumber, counts.get(valueNumber) ?? 0]),
    ),
    invalid,
  };
};

export const formatDuplicateReport = (analysis) => {
  const lines = [
    `Total numbers: ${analysis.total}`,
    `Unique numbers: ${analysis.unique}`,
    `Duplicates found: ${analysis.duplicateCount}`,
    "",
  ];

  if (analysis.duplicates.length > 0) {
    lines.push(
      `Duplicate values: ${analysis.duplicates
        .map((valueNumber) => `${valueNumber} (x${analysis.duplicateOccurrences[valueNumber] ?? 0})`)
        .join(", ")}`,
    );
  } else {
    lines.push("No duplicates found.");
  }

  if (analysis.invalid.length > 0) {
    lines.push("");
    lines.push(`Skipped non-numeric lines: ${analysis.invalid.join(", ")}`);
  }

  return lines.join("\n");
};

export const getTrimmedLines = (value) =>
  value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

export const formatNumbers = (value) => getTrimmedLines(value).join(", ");

export const formatNumbersWithQuotes = (value) =>
  getTrimmedLines(value)
    .map((line) => `'${line}'`)
    .join(",");

export function getDayCoverageStatus(logDay, csvDay) {
  const hasPair = Boolean(logDay?.acs1 && logDay?.acs2);
  if (!csvDay) {
    return { complete: false, label: hasPair ? "Not parsed" : "Incomplete" };
  }
  if (hasPair && csvDay.fullDay) {
    return { complete: true, label: "Complete" };
  }
  return { complete: false, label: "Parsed" };
}

export function buildCoverageDays(files, logDays, csvDays) {
  const logDayByDate = new Map((logDays || []).map((day) => [day.date, day]));
  const csvDayByDate = new Map((csvDays || []).map((day) => [day.date, day]));
  const filesByDate = new Map();

  for (const file of files || []) {
    if (!filesByDate.has(file.logDate)) {
      filesByDate.set(file.logDate, []);
    }
    filesByDate.get(file.logDate).push(file);
  }

  const dates = new Set([
    ...filesByDate.keys(),
    ...(logDays || []).map((day) => day.date),
    ...(csvDays || []).map((day) => day.date),
  ]);

  return [...dates]
    .sort((left, right) => right.localeCompare(left))
    .map((date) => {
      const dayFiles = filesByDate.get(date) || [];
      const logDay = logDayByDate.get(date) || {
        acs1: dayFiles.some((file) => file.acsNode === "acs1"),
        acs2: dayFiles.some((file) => file.acsNode === "acs2"),
      };
      const csvDay = csvDayByDate.get(date) || null;
      const coverage = getDayCoverageStatus(logDay, csvDay);
      return {
        date,
        files: dayFiles,
        logDay,
        csvDay,
        complete: coverage.complete,
        statusLabel: coverage.label,
      };
    });
}

export function summarizeCoverage(coverageDays) {
  const days = coverageDays || [];
  const withLogs = days.filter((day) => day.logDay?.acs1 || day.logDay?.acs2).length;
  const withPair = days.filter((day) => day.logDay?.acs1 && day.logDay?.acs2).length;
  const complete = days.filter((day) => day.complete).length;
  const parsed = days.filter((day) => day.csvDay).length;
  const totalRows = days.reduce((sum, day) => sum + (day.csvDay?.rowCount || 0), 0);
  return { withLogs, withPair, complete, parsed, totalRows, totalDays: days.length };
}

export function sortLogFilesForUpload(files) {
  return [...files].sort((left, right) => {
    const leftDates = extractLogDatesFromNames([left.name]);
    const rightDates = extractLogDatesFromNames([right.name]);
    const leftDate = leftDates[0] || "";
    const rightDate = rightDates[0] || "";
    if (leftDate !== rightDate) {
      return leftDate.localeCompare(rightDate);
    }
    const leftNode = detectAcsNode(left.name) === "acs2" ? 1 : 0;
    const rightNode = detectAcsNode(right.name) === "acs2" ? 1 : 0;
    return leftNode - rightNode;
  });
}

export function detectAcsNode(fileName) {
  const lowered = fileName.toLowerCase();
  if (lowered.includes("acs1")) {
    return "acs1";
  }
  if (lowered.includes("acs2")) {
    return "acs2";
  }
  return null;
}

export function extractLogDatesFromNames(fileNames) {
  return [
    ...new Set(
      fileNames.flatMap((fileName) => [...fileName.matchAll(/(\d{4}-\d{2}-\d{2})/g)].map((match) => match[1])),
    ),
  ].sort();
}

export function groupQueueByDate(queueItems) {
  const byDate = new Map();

  for (const item of queueItems) {
    const dateMatch = item.filename.match(/(\d{4}-\d{2}-\d{2})/);
    const date = item.logDate || dateMatch?.[1];
    if (!date) {
      continue;
    }
    if (!byDate.has(date)) {
      byDate.set(date, []);
    }
    byDate.get(date).push(item);
  }

  return [...byDate.entries()].sort(([left], [right]) => left.localeCompare(right));
}

export function validateQueuePairs(queueItems) {
  const byDate = new Map();

  for (const item of queueItems) {
    const node = item.acsNode || detectAcsNode(item.filename);
    if (!node) {
      return `Log file name must include ACS1 or ACS2: ${item.filename}`;
    }

    const dateMatch = item.filename.match(/(\d{4}-\d{2}-\d{2})/);
    if (!dateMatch) {
      return `Cannot detect date in log file name: ${item.filename}`;
    }

    const date = item.logDate || dateMatch[1];
    if (!byDate.has(date)) {
      byDate.set(date, new Set());
    }
    byDate.get(date).add(node);
  }

  const missingPairs = [...byDate.entries()]
    .filter(([, nodes]) => !(nodes.has("acs1") && nodes.has("acs2")))
    .map(([date]) => date)
    .sort();

  if (missingPairs.length) {
    return `Each date must include both ACS1 and ACS2 logs. Missing pair for: ${missingPairs.join(", ")}`;
  }

  return "";
}

export function buildFileNameFromQueue(queueItems) {
  const dates = extractLogDatesFromNames(queueItems.map((item) => item.filename));
  if (!dates.length) {
    return null;
  }
  const prefix = "3ds-messages";
  if (dates.length === 1) {
    return `${prefix}-${dates[0]}-parser.csv`;
  }
  return `${prefix}-${dates[0]}-to-${dates[dates.length - 1]}-parser.csv`;
}

export function resolveDownloadFileName(payloadFileName, fallbackName) {
  if (payloadFileName && !payloadFileName.includes("-extracted")) {
    return payloadFileName;
  }
  return fallbackName || payloadFileName || "3ds-messages-parser.csv";
}

export function getAcsNodeStyle(acsNode, theme) {
  if (acsNode === "acs1") {
    return {
      borderColor: theme.palette.primary.main,
      chipColor: "primary",
      label: "ACS1",
    };
  }
  if (acsNode === "acs2") {
    return {
      borderColor: theme.palette.secondary.main,
      chipColor: "secondary",
      label: "ACS2",
    };
  }
  return {
    borderColor: theme.palette.warning.main,
    chipColor: "warning",
    label: "Unknown",
  };
}

export function mergeQueueItems(current, incoming) {
  const unique = new Map();
  [...current, ...incoming].forEach((item) => {
    unique.set(item.id, item);
  });
  return Array.from(unique.values()).sort((left, right) => {
    const leftDate = left.logDate || "";
    const rightDate = right.logDate || "";
    if (leftDate !== rightDate) {
      return leftDate.localeCompare(rightDate);
    }
    return (left.acsNode || "").localeCompare(right.acsNode || "");
  });
}

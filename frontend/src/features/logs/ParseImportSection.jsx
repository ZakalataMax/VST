import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  LinearProgress,
  Stack,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import CloseIcon from "@mui/icons-material/Close";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchLogDays, fetchLogFiles, parseStoredLogs, runMerchantWindowTest, uploadLog } from "./api";
import {
  buildCoverageDays,
  buildFileNameFromQueue,
  getAcsNodeStyle,
  mergeQueueItems,
  resolveDownloadFileName,
  groupQueueByDate,
  sortLogFilesForUpload,
  validateQueuePairs,
} from "./logUtils";

function downloadCsvFile(csv, fileName) {
  const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName || "3ds-messages-parser.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function QueueFileBlock({ item, onRemove }) {
  const theme = useTheme();
  const style = getAcsNodeStyle(item.acsNode, theme);

  return (
    <Box
      sx={{
        width: 172,
        flexShrink: 0,
        px: 1.25,
        py: 1,
        borderRadius: 2,
        border: "1px solid",
        borderColor: alpha(style.borderColor, 0.45),
        bgcolor: alpha(style.borderColor, 0.08),
        position: "relative",
      }}
    >
      <IconButton
        size="small"
        onClick={() => onRemove(item.id)}
        sx={{
          position: "absolute",
          top: 2,
          right: 2,
          p: 0.25,
          color: "text.secondary",
        }}
      >
        <CloseIcon sx={{ fontSize: 14 }} />
      </IconButton>
      <Chip
        label={style.label}
        color={style.chipColor}
        size="small"
        sx={{ height: 20, fontSize: 10, fontWeight: 700, mb: 0.75 }}
      />
      <Typography
        variant="caption"
        sx={{
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
          fontWeight: 600,
          lineHeight: 1.35,
          pr: 2,
          wordBreak: "break-all",
        }}
        title={item.filename}
      >
        {item.filename}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.25 }}>
        {(item.fileSize / 1024 / 1024).toFixed(1)} MB
      </Typography>
    </Box>
  );
}

function SavedDayRow({ day, queueIds, onAddDay }) {
  const theme = useTheme();
  const acs1 = getAcsNodeStyle("acs1", theme);
  const acs2 = getAcsNodeStyle("acs2", theme);
  const hasPair = day.logDay?.acs1 && day.logDay?.acs2;
  const inQueue = day.files.length > 0 && day.files.every((file) => queueIds.has(file.id));

  return (
    <Stack
      direction="row"
      spacing={1}
      alignItems="center"
      sx={{
        px: 1.25,
        py: 0.85,
        borderRadius: 2,
        border: "1px solid",
        borderColor: inQueue ? alpha(theme.palette.primary.main, 0.5) : "divider",
        bgcolor: inQueue ? alpha(theme.palette.primary.main, 0.08) : "transparent",
      }}
    >
      <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 92, fontSize: 13 }}>
        {day.date}
      </Typography>
      <Chip
        label="ACS1"
        size="small"
        sx={{
          height: 22,
          fontSize: 10,
          fontWeight: 700,
          bgcolor: day.logDay?.acs1 ? alpha(acs1.borderColor, 0.2) : alpha(theme.palette.text.primary, 0.06),
          color: day.logDay?.acs1 ? acs1.borderColor : "text.disabled",
        }}
      />
      <Chip
        label="ACS2"
        size="small"
        sx={{
          height: 22,
          fontSize: 10,
          fontWeight: 700,
          bgcolor: day.logDay?.acs2 ? alpha(acs2.borderColor, 0.2) : alpha(theme.palette.text.primary, 0.06),
          color: day.logDay?.acs2 ? acs2.borderColor : "text.disabled",
        }}
      />
      <Box sx={{ flex: 1 }} />
      <Button
        size="small"
        variant={inQueue ? "outlined" : "text"}
        startIcon={<AddIcon />}
        disabled={!hasPair || inQueue}
        onClick={() => onAddDay(day.files)}
        sx={{ minWidth: 0, px: 1 }}
      >
        {inQueue ? "Queued" : "Queue"}
      </Button>
    </Stack>
  );
}

function SavedLogsPanel({ days, queueIds, onAddDay, expanded, onToggle, loading, refreshing }) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        overflow: "hidden",
        bgcolor: alpha(theme.palette.background.default, 0.35),
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.5}
        onClick={onToggle}
        sx={{
          px: 1.25,
          py: 0.75,
          cursor: "pointer",
          userSelect: "none",
          borderBottom: expanded ? "1px solid" : "none",
          borderColor: "divider",
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.06) },
        }}
      >
        <IconButton
          size="small"
          onClick={(event) => {
            event.stopPropagation();
            onToggle();
          }}
          sx={{ p: 0.25, color: "text.secondary" }}
        >
          {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
        <Typography variant="subtitle2" sx={{ flex: 1 }}>
          Saved on server
        </Typography>
        {!loading && days.length > 0 ? (
          <Chip label={days.length} size="small" sx={{ height: 22, fontSize: 11, minWidth: 28 }} />
        ) : null}
      </Stack>

      <Collapse in={expanded}>
        {refreshing ? <LinearProgress sx={{ height: 2 }} /> : null}
        {loading && !days.length ? (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 1.5, py: 1.5 }}>
            <CircularProgress size={18} />
            <Typography variant="caption" color="text.secondary">
              Loading saved logs...
            </Typography>
          </Stack>
        ) : days.length > 0 ? (
          <Box sx={{ px: 1.25, py: 1, opacity: refreshing ? 0.72 : 1, transition: "opacity 0.2s ease" }}>
            <Stack spacing={0.75}>
              {days.map((day) => (
                <SavedDayRow key={day.date} day={day} queueIds={queueIds} onAddDay={onAddDay} />
              ))}
            </Stack>
          </Box>
        ) : (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", px: 1.5, py: 1.5 }}>
            No saved logs yet.
          </Typography>
        )}
      </Collapse>
    </Box>
  );
}

export default function ParseImportSection({
  queue,
  onQueueChange,
  onParseComplete,
  onError,
  onLogsUploaded,
  errorText,
  logsRefreshKey,
}) {
  const theme = useTheme();
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [windowTesting, setWindowTesting] = useState(false);
  const [savedFiles, setSavedFiles] = useState([]);
  const [logDays, setLogDays] = useState([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [savedRefreshing, setSavedRefreshing] = useState(false);
  const [savedExpanded, setSavedExpanded] = useState(true);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [parseProgress, setParseProgress] = useState(null);
  const hasSavedDataRef = useRef(false);

  const queueIds = useMemo(() => new Set(queue.map((item) => item.id)), [queue]);

  const reloadSavedData = useCallback(async () => {
    const blockUi = !hasSavedDataRef.current;
    if (blockUi) {
      setSavedLoading(true);
    } else {
      setSavedRefreshing(true);
    }
    try {
      const logDaysPayload = await fetchLogDays();
      setLogDays(logDaysPayload.days || []);
      const filesPayload = await fetchLogFiles();
      setSavedFiles(filesPayload.files || []);
      hasSavedDataRef.current = true;
    } catch {
      if (blockUi) {
        setSavedFiles([]);
        setLogDays([]);
      }
    } finally {
      setSavedLoading(false);
      setSavedRefreshing(false);
    }
  }, []);

  useEffect(() => {
    reloadSavedData();
  }, [logsRefreshKey, reloadSavedData]);

  const savedDays = useMemo(() => buildCoverageDays(savedFiles, logDays, []), [savedFiles, logDays]);

  const uploadFiles = useCallback(
    async (incomingFiles) => {
      if (!incomingFiles.length) {
        return;
      }
      const ordered = sortLogFilesForUpload(incomingFiles);
      setUploading(true);
      onError("");
      try {
        for (let index = 0; index < ordered.length; index += 1) {
          const file = ordered[index];
          setUploadProgress({ current: index + 1, total: ordered.length, name: file.name });
          await uploadLog(file);
          onLogsUploaded();
        }
      } catch (error) {
        onError(error.message || "Upload failed.");
      } finally {
        setUploading(false);
        setUploadProgress(null);
      }
    },
    [onError, onLogsUploaded],
  );

  const handleFileInput = async (event) => {
    const selected = Array.from(event.target.files || []).filter((file) => file.name.toLowerCase().endsWith(".log"));
    event.target.value = "";
    if (!selected.length) {
      onError("Only .log files are supported.");
      return;
    }
    await uploadFiles(selected);
  };

  const handleDrop = async (event) => {
    event.preventDefault();
    setDragActive(false);
    const dropped = Array.from(event.dataTransfer.files || []).filter((file) =>
      file.name.toLowerCase().endsWith(".log"),
    );
    if (!dropped.length) {
      onError("Only .log files are supported.");
      return;
    }
    await uploadFiles(dropped);
  };

  const addDayToQueue = (files) => {
    onQueueChange((current) =>
      mergeQueueItems(
        current,
        files.map((file) => ({
          id: file.id,
          filename: file.filename,
          logDate: file.logDate,
          acsNode: file.acsNode,
          fileSize: file.fileSize,
        })),
      ),
    );
  };

  const removeFromQueue = (fileId) => {
    onQueueChange((current) => current.filter((item) => item.id !== fileId));
  };

  const handleWindowTest = async () => {
    if (!queue.length) {
      onError("Add at least one log file to the parse queue.");
      return;
    }
    const pairError = validateQueuePairs(queue);
    if (pairError) {
      onError(pairError);
      return;
    }

    setWindowTesting(true);
    onError("");
    try {
      const payload = await runMerchantWindowTest(queue.map((item) => item.id));
      downloadCsvFile(payload.csv, payload.fileName || "report-merchant-window.csv");
      onParseComplete({
        savedCsvDays: [{ date: payload.date, rowCount: payload.rowCount }],
        windowTest: {
          qualifyingTxnCount: payload.qualifyingTxnCount,
          rowCount: payload.rowCount,
          savedPath: payload.savedPath,
        },
      });
    } catch (error) {
      onError(error.message || "Window test failed.");
    } finally {
      setWindowTesting(false);
    }
  };

  const handleParse = async () => {
    if (!queue.length) {
      onError("Add at least one log file to the parse queue.");
      return;
    }
    const pairError = validateQueuePairs(queue);
    if (pairError) {
      onError(pairError);
      return;
    }

    const dayGroups = groupQueueByDate(queue);
    setParsing(true);
    onError("");
    let lastPayload = null;
    const savedCsvDays = [];
    try {
      for (let index = 0; index < dayGroups.length; index += 1) {
        const [date, items] = dayGroups[index];
        setParseProgress({ current: index + 1, total: dayGroups.length, date });
        const payload = await parseStoredLogs(items.map((item) => item.id));
        lastPayload = payload;
        savedCsvDays.push(...(payload.savedCsvDays || []));
        onParseComplete({ savedCsvDays: [...savedCsvDays] });
      }
      if (dayGroups.length === 1 && lastPayload?.csv) {
        const fallbackName = buildFileNameFromQueue(queue);
        const finalName = resolveDownloadFileName(lastPayload.fileName, fallbackName);
        downloadCsvFile(lastPayload.csv, finalName);
      }
    } catch (error) {
      onError(error.message || "Parse failed.");
    } finally {
      setParsing(false);
      setParseProgress(null);
    }
  };

  const busy = uploading || parsing || windowTesting;
  const contentRef = useRef(null);

  const scrollToTop = () => {
    contentRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <Card ref={contentRef} variant="outlined">
      <Box
        onClick={scrollToTop}
        sx={{
          px: 2,
          pt: 2,
          pb: 1.5,
          cursor: "pointer",
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.06) },
        }}
      >
        <Typography variant="h6">Parse</Typography>
        <Typography variant="body2" color="text.secondary">
          Drop ACS1 and ACS2 .log files here. Queue saved days, then Parse.
        </Typography>
      </Box>
      <CardContent sx={{ pt: "16px !important" }}>
        <Stack spacing={2}>
          <Box
            onDragEnter={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              const next = event.relatedTarget;
              if (next && event.currentTarget.contains(next)) {
                return;
              }
              setDragActive(false);
            }}
            onDrop={handleDrop}
            sx={{
              border: "2px dashed",
              borderColor: dragActive ? "primary.main" : "divider",
              borderRadius: 2,
              p: 3,
              textAlign: "center",
              bgcolor: dragActive ? alpha(theme.palette.primary.main, 0.08) : "transparent",
              transition: "border-color 0.15s ease, background-color 0.15s ease",
            }}
          >
            <Stack spacing={1.5} alignItems="center">
              <AttachFileIcon color={dragActive ? "primary" : "action"} sx={{ fontSize: 32 }} />
              <Typography variant="body2">{dragActive ? "Release to upload" : "Drop .log files here"}</Typography>
              <Button variant="outlined" component="label" size="small" disabled={busy}>
                Choose files
                <input hidden multiple type="file" accept=".log" onChange={handleFileInput} />
              </Button>
            </Stack>
          </Box>

          <SavedLogsPanel
            days={savedDays}
            queueIds={queueIds}
            onAddDay={addDayToQueue}
            expanded={savedExpanded}
            onToggle={() => setSavedExpanded((value) => !value)}
            loading={savedLoading}
            refreshing={savedRefreshing}
          />

          {uploadProgress ? (
            <Typography variant="caption" color="text.secondary">
              Uploading {uploadProgress.current}/{uploadProgress.total}: {uploadProgress.name}
            </Typography>
          ) : null}
          {parseProgress ? (
            <Typography variant="caption" color="text.secondary">
              Parsing day {parseProgress.current}/{parseProgress.total}: {parseProgress.date}
            </Typography>
          ) : null}

          {queue.length > 0 && (
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Parse queue ({queue.length})
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                {queue.map((item) => (
                  <QueueFileBlock key={item.id} item={item} onRemove={removeFromQueue} />
                ))}
              </Box>
            </Box>
          )}

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
            <Button variant="contained" onClick={handleParse} disabled={busy || !queue.length}>
              {parsing
                ? parseProgress
                  ? `Parsing ${parseProgress.current}/${parseProgress.total}...`
                  : "Parsing..."
                : uploading
                  ? uploadProgress
                    ? `Uploading ${uploadProgress.current}/${uploadProgress.total}...`
                    : "Uploading..."
                  : "Parse"}
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleWindowTest}
              disabled={busy || !queue.length}
            >
              {windowTesting ? "Window test..." : "Test 11–15 report"}
            </Button>
            {busy && <CircularProgress size={24} />}
          </Stack>
          <Typography variant="caption" color="text.secondary">
            Test 11–15: card+acquirerMerchantID, Y*3 less than others; CSV only txns with no CRes in chain.
          </Typography>

          {errorText ? <Alert severity="error">{errorText}</Alert> : null}
        </Stack>
      </CardContent>
    </Card>
  );
}

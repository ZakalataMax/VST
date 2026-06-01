import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import { fetchCsvDays, fetchReportTemplate, runReport, summarizeCsvDays } from "../report/api";
import { downloadResultsCsv } from "./reportCsv";
import { scrollSx } from "../../theme/scrollStyles";

const CHUNK_SIZE = 100;

function isExpandableColumn(column) {
  return column.toLowerCase().includes("timeline");
}

function getColumnMaxWidth(column) {
  if (isExpandableColumn(column)) {
    return 200;
  }
  return 280;
}

function CellDetailDialog({ open, title, value, onClose }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ pb: 1 }}>{title}</DialogTitle>
      <DialogContent dividers sx={{ ...scrollSx }}>
        <Typography
          component="pre"
          sx={{
            m: 0,
            fontFamily: "monospace",
            fontSize: 13,
            lineHeight: 1.55,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {value || "—"}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function ReportTable({ columns, rows, scrollRef, loadingMore, sentinelRef, hasMore }) {
  const theme = useTheme();
  const [cellDetail, setCellDetail] = useState(null);

  const openCellDetail = (column, value) => {
    setCellDetail({ column, value: String(value ?? "") });
  };

  return (
    <>
      <CellDetailDialog
        open={Boolean(cellDetail)}
        title={cellDetail?.column ?? ""}
        value={cellDetail?.value ?? ""}
        onClose={() => setCellDetail(null)}
      />
    <TableContainer
      ref={scrollRef}
      sx={{
        ...scrollSx,
        maxHeight: "min(70vh, 720px)",
        border: "1px solid",
        borderColor: alpha(theme.palette.divider, 0.9),
        borderRadius: 2,
        bgcolor: alpha(theme.palette.background.default, 0.45),
      }}
    >
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell
                key={column}
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  letterSpacing: 0.4,
                  textTransform: "uppercase",
                  color: "text.secondary",
                  bgcolor: alpha(theme.palette.primary.main, 0.1),
                  borderBottom: `1px solid ${alpha(theme.palette.primary.main, 0.25)}`,
                  whiteSpace: "nowrap",
                }}
              >
                {column}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow
              key={`${index}-${row[columns[0]]}`}
              sx={{
                bgcolor: index % 2 === 0 ? "transparent" : alpha(theme.palette.text.primary, 0.03),
                "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.08) },
                "&:last-child td": { borderBottom: 0 },
              }}
            >
              {columns.map((column) => {
                const expandable = isExpandableColumn(column);
                const cellValue = row[column];
                const maxWidth = getColumnMaxWidth(column);

                return (
                  <TableCell
                    key={column}
                    onClick={expandable ? () => openCellDetail(column, cellValue) : undefined}
                    sx={{
                      fontSize: 12,
                      py: 0.85,
                      whiteSpace: "nowrap",
                      fontFamily: expandable ? "inherit" : "monospace",
                      maxWidth,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      cursor: expandable ? "pointer" : "default",
                      ...(expandable && {
                        "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.12) },
                      }),
                    }}
                  >
                    {cellValue}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
          {hasMore ? (
            <TableRow>
              <TableCell colSpan={columns.length || 1} ref={sentinelRef} sx={{ border: 0, py: 1.5 }}>
                {loadingMore ? (
                  <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
                    <CircularProgress size={16} />
                    <Typography variant="caption" color="text.secondary">
                      Loading more rows...
                    </Typography>
                  </Stack>
                ) : (
                  <Typography variant="caption" color="text.secondary" align="center" display="block">
                    Scroll for more
                  </Typography>
                )}
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </TableContainer>
    </>
  );
}

export default function ReportSection({
  parseSummary,
  errorText,
  onError,
  selectedDay,
  refreshKey,
}) {
  const [reportLoading, setReportLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exportingAll, setExportingAll] = useState(false);
  const [csvStatus, setCsvStatus] = useState(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [useTxnId, setUseTxnId] = useState(false);
  const [txnId, setTxnId] = useState("");
  const [useCustomSql, setUseCustomSql] = useState(false);
  const [customSql, setCustomSql] = useState("");
  const [customSqlLoaded, setCustomSqlLoaded] = useState(false);
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [hasMore, setHasMore] = useState(false);

  const scrollRef = useRef(null);
  const sentinelRef = useRef(null);
  const prefetchRef = useRef(null);
  const queryRef = useRef(null);
  const loadingMoreRef = useRef(false);

  useEffect(() => {
    loadingMoreRef.current = loadingMore;
  }, [loadingMore]);

  useEffect(() => {
    fetchCsvDays()
      .then((payload) => {
        const status = summarizeCsvDays(payload.days);
        setCsvStatus(status);
        if (!dateFrom && status?.minDate) {
          setDateFrom(`${status.minDate} 00:00:00.000`);
        }
        if (!dateTo && status?.maxDate) {
          setDateTo(`${status.maxDate} 23:59:59.999`);
        }
      })
      .catch(() => {
        setCsvStatus(null);
      });
  }, [refreshKey]);

  useEffect(() => {
    if (selectedDay) {
      setDateFrom(`${selectedDay} 00:00:00.000`);
      setDateTo(`${selectedDay} 23:59:59.999`);
    }
  }, [selectedDay]);

  useEffect(() => {
    const savedDays = parseSummary?.savedCsvDays;
    if (!savedDays?.length) {
      return;
    }
    const sorted = [...savedDays].sort((left, right) => left.date.localeCompare(right.date));
    setDateFrom(`${sorted[0].date} 00:00:00.000`);
    setDateTo(`${sorted[sorted.length - 1].date} 23:59:59.999`);
  }, [parseSummary]);

  const buildReportBody = useCallback(
    (nextOffset = 0) => {
      if (useCustomSql) {
        return { mode: "custom", sql: customSql, limit: CHUNK_SIZE, offset: nextOffset };
      }
      if (useTxnId) {
        return {
          mode: "txnId",
          txnId: txnId.trim(),
          dateFrom: dateFrom.trim() || null,
          dateTo: dateTo.trim() || null,
          limit: CHUNK_SIZE,
          offset: nextOffset,
        };
      }
      return {
        mode: "date",
        dateFrom: dateFrom.trim(),
        dateTo: dateTo.trim() || null,
        limit: CHUNK_SIZE,
        offset: nextOffset,
      };
    },
    [customSql, dateFrom, dateTo, txnId, useCustomSql, useTxnId],
  );

  queryRef.current = buildReportBody;

  const fetchChunk = useCallback(async (nextOffset) => {
    return runReport(queryRef.current(nextOffset));
  }, []);

  const schedulePrefetch = useCallback(
    (nextOffset) => {
      prefetchRef.current = fetchChunk(nextOffset);
    },
    [fetchChunk],
  );

  const loadMore = useCallback(async () => {
    if (loadingMore || reportLoading || !hasMore) {
      return;
    }
    setLoadingMore(true);
    onError("");
    try {
      const nextOffset = rows.length;
      let payload;
      if (prefetchRef.current) {
        payload = await prefetchRef.current;
        prefetchRef.current = null;
      } else {
        payload = await fetchChunk(nextOffset);
      }
      setColumns(payload.columns || []);
      setRows((current) => [...current, ...(payload.rows || [])]);
      const chunkLength = (payload.rows || []).length;
      const total = payload.rowCount ?? chunkLength;
      const more = nextOffset + chunkLength < total;
      setHasMore(more);
      if (more) {
        schedulePrefetch(nextOffset + chunkLength);
      }
    } catch (error) {
      onError(error.message || "Failed to load more rows.");
    } finally {
      setLoadingMore(false);
    }
  }, [fetchChunk, hasMore, loadingMore, onError, reportLoading, rows.length, schedulePrefetch]);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root || !rows.length || !hasMore) {
      return undefined;
    }

    const tryLoadNearBottom = () => {
      if (loadingMoreRef.current || reportLoading || !hasMore) {
        return;
      }
      const remaining = root.scrollHeight - root.scrollTop - root.clientHeight;
      if (remaining > 160) {
        return;
      }
      loadMore();
    };

    root.addEventListener("scroll", tryLoadNearBottom, { passive: true });
    return () => root.removeEventListener("scroll", tryLoadNearBottom);
  }, [hasMore, loadMore, reportLoading, rows.length]);

  const ensureCustomSql = async () => {
    if (customSqlLoaded) {
      return;
    }
    const payload = await fetchReportTemplate();
    setCustomSql(payload.sql || "");
    setCustomSqlLoaded(true);
  };

  const handleRunReport = async () => {
    if (useCustomSql && !customSql.trim()) {
      onError("Custom SQL is empty.");
      return;
    }
    if (useTxnId && !txnId.trim()) {
      onError("Transaction ID is required.");
      return;
    }
    if (!useCustomSql && !useTxnId && !dateFrom.trim()) {
      onError("Date from is required.");
      return;
    }

    setReportLoading(true);
    onError("");
    prefetchRef.current = null;
    try {
      const payload = await fetchChunk(0);
      setColumns(payload.columns || []);
      setRows(payload.rows || []);
      const chunkLength = (payload.rows || []).length;
      const total = payload.rowCount ?? chunkLength;
      const more = chunkLength < total;
      setHasMore(more);
      if (more) {
        schedulePrefetch(CHUNK_SIZE);
      }
    } catch (error) {
      onError(error.message || "Report failed.");
      setColumns([]);
      setRows([]);
      setHasMore(false);
    } finally {
      setReportLoading(false);
    }
  };

  const handleExportAll = async () => {
    if (!columns.length) {
      return;
    }
    setExportingAll(true);
    onError("");
    try {
      let collected = [...rows];
      let offset = collected.length;
      while (true) {
        const payload = await fetchChunk(offset);
        if (!payload.rows?.length) {
          break;
        }
        collected = [...collected, ...payload.rows];
        offset = collected.length;
        if (payload.rows.length < CHUNK_SIZE) {
          break;
        }
      }
      downloadResultsCsv(columns, collected, "report-full.csv");
    } catch (error) {
      onError(error.message || "Export failed.");
    } finally {
      setExportingAll(false);
    }
  };

  const handleCustomSqlToggle = async (checked) => {
    setUseCustomSql(checked);
    if (checked) {
      try {
        await ensureCustomSql();
      } catch (error) {
        onError(error.message || "Failed to load SQL template.");
      }
    }
  };

  return (
    <Card variant="outlined">
      <CardContent sx={{ pt: 2, pb: "20px !important", "&:last-child": { pb: "20px !important" } }}>
        <Stack spacing={2} sx={{ pb: rows.length ? 0 : 0.5 }}>
            <Box>
              <Typography variant="h6">Report</Typography>
              <Typography variant="body2" color="text.secondary">
                Run report from parsed CSV files on disk. Final report is saved under csv_reports_final.
              </Typography>
            </Box>

            {csvStatus?.rowCount > 0 && (
              <Typography variant="body2" color="text.secondary">
                Parsed CSV: {csvStatus.rowCount.toLocaleString()} rows
                {csvStatus.minDate && csvStatus.maxDate ? ` (${csvStatus.minDate} — ${csvStatus.maxDate})` : ""}
              </Typography>
            )}

            {parseSummary?.savedCsvDays?.length > 0 && (
              <Alert severity="info">
                Last parse: {parseSummary.savedCsvDays.length} day file(s) saved to data/csv
              </Alert>
            )}

            {errorText ? <Alert severity="error">{errorText}</Alert> : null}

            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                label="From"
                placeholder="2026-05-22 or 2026-05-22 00:00:00"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                fullWidth
                size="small"
                disabled={useCustomSql}
              />
              <TextField
                label="To"
                placeholder="2026-05-24 or 2026-05-24 23:59:59"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                fullWidth
                size="small"
                disabled={useCustomSql}
              />
            </Stack>

            <Stack spacing={0.5}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={useTxnId}
                    onChange={(event) => {
                      setUseTxnId(event.target.checked);
                      if (event.target.checked) {
                        setUseCustomSql(false);
                      }
                    }}
                    disabled={useCustomSql}
                  />
                }
                label="Filter by transaction ID"
              />
              <Collapse in={useTxnId && !useCustomSql}>
                <TextField
                  label="Transaction ID"
                  value={txnId}
                  onChange={(event) => setTxnId(event.target.value)}
                  fullWidth
                  size="small"
                  sx={{ mt: 1 }}
                />
              </Collapse>

              <FormControlLabel
                control={
                  <Checkbox checked={useCustomSql} onChange={(event) => handleCustomSqlToggle(event.target.checked)} />
                }
                label="Custom SQL"
              />
              <Collapse in={useCustomSql}>
                <TextField
                  label="SQL"
                  value={customSql}
                  onChange={(event) => setCustomSql(event.target.value)}
                  fullWidth
                  multiline
                  minRows={6}
                  size="small"
                  sx={{ mt: 1 }}
                  slotProps={{ input: { sx: { fontFamily: "monospace", fontSize: 13 } } }}
                />
              </Collapse>
            </Stack>

            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
              <Button variant="contained" onClick={handleRunReport} disabled={reportLoading || exportingAll}>
                {reportLoading ? "Running..." : "Run report"}
              </Button>
              {reportLoading && <CircularProgress size={22} />}
              {rows.length > 0 && (
                <Button variant="outlined" onClick={handleExportAll} disabled={exportingAll || reportLoading}>
                  {exportingAll ? "Exporting..." : "Export full CSV"}
                </Button>
              )}
            </Stack>
        </Stack>

        {rows.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <ReportTable
              columns={columns}
              rows={rows}
              scrollRef={scrollRef}
              loadingMore={loadingMore}
              sentinelRef={sentinelRef}
              hasMore={hasMore}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

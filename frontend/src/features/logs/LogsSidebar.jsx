import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Chip,
  CircularProgress,
  IconButton,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import { fetchLogDays, fetchLogFiles } from "./api";
import { fetchDbDays } from "../report/api";
import { buildCoverageDays } from "./logUtils";
import { scrollSx } from "../../theme/scrollStyles";

export const SIDEBAR_WIDTH = 268;
export const SIDEBAR_RAIL_WIDTH = 52;

function DayGroup({ day, selected, onSelectDay }) {
  const theme = useTheme();
  const accent = day.complete
    ? theme.palette.success.main
    : day.dbDay
      ? theme.palette.warning.main
      : day.logDay?.acs1 && day.logDay?.acs2
        ? theme.palette.info.main
        : theme.palette.text.disabled;

  const minTime = day.dbDay?.minDateTime?.length >= 19 ? day.dbDay.minDateTime.slice(11, 19) : null;
  const maxTime = day.dbDay?.maxDateTime?.length >= 19 ? day.dbDay.maxDateTime.slice(11, 19) : null;

  return (
    <Box
      sx={{
        p: 1.25,
        borderRadius: 2,
        border: "1px solid",
        borderColor: selected ? alpha(theme.palette.primary.main, 0.5) : alpha(accent, 0.35),
        bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : alpha(accent, 0.06),
        boxShadow: selected ? `inset 3px 0 0 ${theme.palette.primary.main}` : `inset 3px 0 0 ${accent}`,
      }}
    >
      <Stack
        direction="row"
        spacing={0.75}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        onClick={() => onSelectDay(day.date)}
        sx={{ mb: day.dbDay ? 0.5 : 0, cursor: "pointer" }}
      >
        <Typography variant="caption" sx={{ fontWeight: 700, fontSize: 12 }}>
          {day.date}
        </Typography>
        <Chip
          label={day.statusLabel}
          size="small"
          color={day.complete ? "success" : day.dbDay ? "warning" : "default"}
          variant="outlined"
          sx={{ height: 20, fontSize: 10, fontWeight: 600 }}
        />
      </Stack>

      {day.dbDay ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
          {day.dbDay.rowCount.toLocaleString()} rows
          {minTime && maxTime ? ` · ${minTime}–${maxTime}` : ""}
        </Typography>
      ) : !(day.logDay?.acs1 && day.logDay?.acs2) ? (
        <Typography variant="caption" color="text.secondary">
          Missing ACS1 or ACS2 file
        </Typography>
      ) : null}
    </Box>
  );
}

function PanelLoader() {
  return (
    <Stack alignItems="center" spacing={1.5} sx={{ py: 4 }}>
      <CircularProgress size={22} thickness={5} />
      <Typography variant="caption" color="text.secondary">
        Loading...
      </Typography>
    </Stack>
  );
}

function SidebarRail({ onToggle }) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 1.5,
        gap: 1.5,
        bgcolor: alpha(theme.palette.background.paper, 0.96),
      }}
    >
      <Tooltip title="Show coverage panel" placement="right">
        <IconButton
          onClick={onToggle}
          size="small"
          sx={{
            width: 28,
            height: 20,
            borderRadius: 999,
            border: "1px solid",
            borderColor: "divider",
            bgcolor: alpha(theme.palette.primary.main, 0.08),
            "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.16) },
          }}
        >
          <ChevronRightIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Tooltip>

      <Box
        sx={{
          width: 32,
          height: 32,
          borderRadius: 1.5,
          display: "grid",
          placeItems: "center",
          bgcolor: alpha(theme.palette.primary.main, 0.12),
          color: "primary.main",
        }}
      >
        <InsightsOutlinedIcon sx={{ fontSize: 18 }} />
      </Box>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          writingMode: "vertical-rl",
          transform: "rotate(180deg)",
          letterSpacing: 1,
          fontSize: 10,
          fontWeight: 600,
          userSelect: "none",
          mt: "auto",
        }}
      >
        Coverage
      </Typography>
    </Box>
  );
}

export default function LogsSidebar({ open, onToggle, logsRefreshKey, dbRefreshKey, selectedDbDay, onSelectDbDay }) {
  const theme = useTheme();
  const [savedFiles, setSavedFiles] = useState([]);
  const [logDays, setLogDays] = useState([]);
  const [dbDays, setDbDays] = useState([]);
  const [loading, setLoading] = useState(false);
  const daysScrollRef = useRef(null);

  const scrollDaysToTop = () => {
    daysScrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchLogFiles(), fetchLogDays(), fetchDbDays()])
      .then(([filesPayload, logDaysPayload, dbDaysPayload]) => {
        setSavedFiles(filesPayload.files || []);
        setLogDays(logDaysPayload.days || []);
        setDbDays(dbDaysPayload.days || []);
      })
      .catch(() => {
        setSavedFiles([]);
        setLogDays([]);
        setDbDays([]);
      })
      .finally(() => setLoading(false));
  }, [logsRefreshKey, dbRefreshKey]);

  const coverageDays = useMemo(
    () => buildCoverageDays(savedFiles, logDays, dbDays),
    [savedFiles, logDays, dbDays],
  );

  if (!open) {
    return (
      <Box sx={{ width: "100%", height: "100%", flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
        <SidebarRail onToggle={onToggle} />
      </Box>
    );
  }

  return (
    <Box sx={{ width: "100%", height: "100%", flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
    <Box
      sx={{
        width: "100%",
        height: "100%",
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        bgcolor: alpha(theme.palette.background.paper, 0.96),
        backgroundImage: (t) => `linear-gradient(180deg, ${alpha(t.palette.primary.main, 0.05)} 0%, transparent 36%)`,
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        onClick={scrollDaysToTop}
        sx={{
          mx: 2,
          mt: 1.5,
          mb: 1,
          px: 1.5,
          py: 1,
          flexShrink: 0,
          borderRadius: 2,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: alpha(theme.palette.background.default, 0.45),
          cursor: "pointer",
          zIndex: 2,
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.08) },
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0, pr: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.3 }}>
            Coverage
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Click a day to filter the report
          </Typography>
        </Box>
        <Tooltip title="Hide panel">
          <IconButton
            onClick={(event) => {
              event.stopPropagation();
              onToggle();
            }}
            size="small"
            sx={{
              flexShrink: 0,
              width: 34,
              height: 22,
              borderRadius: 999,
              border: "1px solid",
              borderColor: "divider",
              bgcolor: alpha(theme.palette.background.paper, 0.8),
              "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.12) },
            }}
          >
            <ChevronLeftIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </Stack>

      {loading && (
        <LinearProgress sx={{ flexShrink: 0, height: 2, bgcolor: alpha(theme.palette.primary.main, 0.08) }} />
      )}

      <Box ref={daysScrollRef} sx={{ flex: 1, minHeight: 0, height: 0, ...scrollSx, px: 2, pb: 2 }}>
        {loading ? (
          <PanelLoader />
        ) : coverageDays.length ? (
          <Stack spacing={1}>
            {coverageDays.map((day) => (
              <DayGroup
                key={day.date}
                day={day}
                selected={selectedDbDay === day.date}
                onSelectDay={(date) => onSelectDbDay(selectedDbDay === date ? "" : date)}
              />
            ))}
          </Stack>
        ) : (
          <Box
            sx={{
              px: 1.5,
              py: 2.5,
              borderRadius: 2,
              border: "1px dashed",
              borderColor: "divider",
              textAlign: "center",
            }}
          >
            <Typography variant="caption" color="text.secondary">
              No data yet. Upload logs on the right.
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
    </Box>
  );
}

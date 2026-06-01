import { useCallback, useState } from "react";
import { Box } from "@mui/material";
import LogsSidebar, { SIDEBAR_RAIL_WIDTH, SIDEBAR_WIDTH } from "./LogsSidebar";
import ParseImportSection from "./ParseImportSection";
import ReportSection from "./ReportSection";

export default function LogsPage() {
  const [queue, setQueue] = useState([]);
  const [parseSummary, setParseSummary] = useState(null);
  const [parseError, setParseError] = useState("");
  const [reportError, setReportError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [logsRefreshKey, setLogsRefreshKey] = useState(0);
  const [csvRefreshKey, setCsvRefreshKey] = useState(0);
  const [selectedDay, setSelectedDay] = useState("");

  const refreshLogs = useCallback(() => {
    setLogsRefreshKey((value) => value + 1);
  }, []);

  const refreshCsv = useCallback(() => {
    setCsvRefreshKey((value) => value + 1);
  }, []);

  const handleParseComplete = useCallback(
    (summary) => {
      setParseSummary(summary);
      refreshLogs();
      refreshCsv();
    },
    [refreshCsv, refreshLogs],
  );

  const sidebarWidth = sidebarOpen ? SIDEBAR_WIDTH : SIDEBAR_RAIL_WIDTH;

  return (
    <Box sx={{ display: "flex", alignItems: "flex-start", my: -2 }}>
      <Box
        sx={{
          width: sidebarWidth,
          flexShrink: 0,
          position: "sticky",
          top: 0,
          alignSelf: "flex-start",
          maxHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
          transition: "width 0.28s cubic-bezier(0.4, 0, 0.2, 1)",
          overflow: "hidden",
        }}
      >
        <LogsSidebar
          open={sidebarOpen}
          onToggle={() => setSidebarOpen((value) => !value)}
          logsRefreshKey={logsRefreshKey}
          csvRefreshKey={csvRefreshKey}
          selectedDay={selectedDay}
          onSelectDay={setSelectedDay}
        />
      </Box>

      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          gap: 2,
          pl: 2,
          pr: 0.5,
          pb: 2,
        }}
      >
        <ParseImportSection
          queue={queue}
          onQueueChange={setQueue}
          onParseComplete={handleParseComplete}
          onError={setParseError}
          onLogsUploaded={refreshLogs}
          errorText={parseError}
          logsRefreshKey={logsRefreshKey}
        />

        <ReportSection
          parseSummary={parseSummary}
          errorText={reportError}
          onError={setReportError}
          selectedDay={selectedDay}
          refreshKey={csvRefreshKey}
        />
      </Box>
    </Box>
  );
}

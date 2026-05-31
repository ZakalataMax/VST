import { useEffect, useState } from "react";
import {
  AppBar,
  Box,
  Container,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from "@mui/material";
import ParsingToolsPage from "./features/parsing/ParsingToolsPage";
import LogsPage from "./features/logs/LogsPage";

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    const saved = window.localStorage.getItem("vst.activeTab");
    return saved === "1" ? 1 : 0;
  });

  useEffect(() => {
    window.localStorage.setItem("vst.activeTab", String(activeTab));
  }, [activeTab]);

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar sx={{ px: { xs: 2, md: 3 } }}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            VST Work Tools
          </Typography>
        </Toolbar>
      </AppBar>
      <Container
        maxWidth="xl"
        sx={{
          py: 2,
          flex: 1,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Tabs
          value={activeTab}
          onChange={(_, value) => setActiveTab(value)}
          sx={{ mb: 2, flexShrink: 0 }}
          variant="scrollable"
          allowScrollButtonsMobile
        >
          <Tab label="Parser" />
          <Tab label="Logs" />
        </Tabs>

        <Box sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {activeTab === 0 ? <ParsingToolsPage /> : <LogsPage />}
        </Box>
      </Container>
    </Box>
  );
}

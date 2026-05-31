import React from "react";
import ReactDOM from "react-dom/client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import App from "./App";
import { globalScrollbarStyles } from "./theme/scrollStyles";

const theme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#0f1115",
      paper: "#171a21",
    },
    primary: {
      main: "#7c9cff",
    },
    secondary: {
      main: "#64d4b0",
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: "Inter, Segoe UI, Roboto, Arial, sans-serif",
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: globalScrollbarStyles,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);

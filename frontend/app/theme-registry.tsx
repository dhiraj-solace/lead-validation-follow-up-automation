"use client";

import { AppRouterCacheProvider } from "@mui/material-nextjs/v14-appRouter";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#0f766e",
      dark: "#115e59",
      light: "#5eead4",
      contrastText: "#ffffff"
    },
    secondary: {
      main: "#c77c2e"
    },
    background: {
      default: "#f5f7fb",
      paper: "#ffffff"
    },
    text: {
      primary: "#172033",
      secondary: "#637083"
    },
    divider: "#dbe3ee"
  },
  shape: {
    borderRadius: 8
  },
  typography: {
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: {
      fontSize: "1.65rem",
      fontWeight: 800,
      lineHeight: 1.15
    },
    h2: {
      fontSize: "1rem",
      fontWeight: 800,
      lineHeight: 1.25
    },
    body1: {
      fontSize: "0.92rem"
    },
    body2: {
      fontSize: "0.82rem"
    },
    button: {
      fontWeight: 800,
      letterSpacing: 0,
      textTransform: "none"
    }
  },
  components: {
    MuiButton: {
      defaultProps: {
        disableElevation: true
      },
      styleOverrides: {
        root: {
          minHeight: 34,
          paddingLeft: 14,
          paddingRight: 14
        }
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: "1px solid #dbe3ee",
          boxShadow: "0 1px 2px rgba(15, 23, 42, 0.06)"
        }
      }
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottomColor: "#e3e9f2",
          fontSize: 13,
          paddingBottom: 10,
          paddingTop: 10
        },
        head: {
          backgroundColor: "#f9fbfd",
          color: "#637083",
          fontSize: 11,
          fontWeight: 800,
          textTransform: "uppercase"
        }
      }
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontSize: 12,
          height: 24
        }
      }
    },
    MuiTextField: {
      defaultProps: {
        size: "small"
      }
    }
  }
});

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    <AppRouterCacheProvider options={{ key: "mui" }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}

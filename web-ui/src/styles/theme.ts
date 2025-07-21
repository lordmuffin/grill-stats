import { createTheme, responsiveFontSizes } from '@mui/material/styles';
import { red, amber, blue, grey } from '@mui/material/colors';
import type { ThemeMode } from '@/types';

// Create theme settings for both light and dark mode
const getDesignTokens = (mode: ThemeMode) => ({
  palette: {
    mode,
    primary: {
      main: mode === 'light' ? '#f44336' : '#ff7961', // Red shades
      light: mode === 'light' ? '#ff7961' : '#ff867c',
      dark: mode === 'light' ? '#ba000d' : '#c62828',
      contrastText: '#fff',
    },
    secondary: {
      main: mode === 'light' ? '#fb8c00' : '#ffb74d', // Orange shades
      light: mode === 'light' ? '#ffbd45' : '#ffe0b2',
      dark: mode === 'light' ? '#c25e00' : '#e65100',
      contrastText: mode === 'light' ? '#000' : '#000',
    },
    error: {
      main: red.A400,
    },
    warning: {
      main: amber[500],
      dark: amber[700],
    },
    info: {
      main: blue[500],
    },
    success: {
      main: '#4caf50',
      dark: '#388e3c',
    },
    background: {
      default: mode === 'light' ? '#f5f5f5' : '#121212',
      paper: mode === 'light' ? '#fff' : '#1e1e1e',
    },
    text: {
      primary: mode === 'light' ? 'rgba(0, 0, 0, 0.87)' : '#fff',
      secondary: mode === 'light' ? 'rgba(0, 0, 0, 0.6)' : 'rgba(255, 255, 255, 0.7)',
      disabled: mode === 'light' ? 'rgba(0, 0, 0, 0.38)' : 'rgba(255, 255, 255, 0.5)',
    },
    divider: mode === 'light' ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)',
    temperature: {
      cold: '#2196f3',
      cool: '#64b5f6',
      warm: '#ff9800',
      hot: '#f44336',
      veryhot: '#d32f2f',
    },
    status: {
      online: '#4caf50',
      offline: grey[500],
      warning: amber[500],
      error: red[500],
    },
  },
  typography: {
    fontFamily: [
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2.5rem',
      fontWeight: 500,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 500,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 500,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 500,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
          padding: '8px 16px',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.2)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: mode === 'light' 
            ? '0px 2px 4px rgba(0, 0, 0, 0.1)' 
            : '0px 2px 4px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: 'none',
          borderBottom: `1px solid ${mode === 'light' ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)'}`,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: mode === 'light' ? '#fff' : '#1e1e1e',
          borderRight: `1px solid ${mode === 'light' ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)'}`,
        },
      },
    },
  },
});

// Create a theme instance.
const baseTheme = createTheme(getDesignTokens('light'));

// Create a responsive theme
export const theme = responsiveFontSizes(baseTheme);

// Create a dark theme
export const darkTheme = responsiveFontSizes(createTheme(getDesignTokens('dark')));

// Helper function to get the appropriate theme for the given mode
export const getTheme = (mode: ThemeMode) => {
  return mode === 'light' ? theme : darkTheme;
};

// Extend the Material-UI theme to include custom properties
declare module '@mui/material/styles' {
  interface Palette {
    temperature: {
      cold: string;
      cool: string;
      warm: string;
      hot: string;
      veryhot: string;
    };
    status: {
      online: string;
      offline: string;
      warning: string;
      error: string;
    };
  }
  
  interface PaletteOptions {
    temperature?: {
      cold: string;
      cool: string;
      warm: string;
      hot: string;
      veryhot: string;
    };
    status?: {
      online: string;
      offline: string;
      warning: string;
      error: string;
    };
  }
}
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { ThemeMode } from '@/types';

interface ThemeState {
  mode: ThemeMode;
  systemPreference: boolean;
}

// Check if system prefers dark mode
const prefersDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

// Check if there's a saved preference in localStorage
const savedMode = localStorage.getItem('theme') as ThemeMode | null;
const savedSystemPref = localStorage.getItem('useSystemTheme');

const initialState: ThemeState = {
  mode: savedMode || (prefersDarkMode ? 'dark' : 'light'),
  systemPreference: savedSystemPref ? savedSystemPref === 'true' : true,
};

const themeSlice = createSlice({
  name: 'theme',
  initialState,
  reducers: {
    setThemeMode: (state, action: PayloadAction<ThemeMode>) => {
      state.mode = action.payload;
      // Save to localStorage
      localStorage.setItem('theme', action.payload);
    },
    toggleThemeMode: (state) => {
      state.mode = state.mode === 'light' ? 'dark' : 'light';
      // Save to localStorage
      localStorage.setItem('theme', state.mode);
    },
    setUseSystemPreference: (state, action: PayloadAction<boolean>) => {
      state.systemPreference = action.payload;
      // Save to localStorage
      localStorage.setItem('useSystemTheme', action.payload.toString());
      
      // If using system preference, update theme to match system
      if (action.payload) {
        const systemTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        state.mode = systemTheme;
        localStorage.setItem('theme', systemTheme);
      }
    },
  },
});

// Export actions
export const { setThemeMode, toggleThemeMode, setUseSystemPreference } = themeSlice.actions;

// Export selectors
export const selectThemeMode = (state: RootState) => state.theme.mode;
export const selectUseSystemPreference = (state: RootState) => state.theme.systemPreference;

export default themeSlice.reducer;
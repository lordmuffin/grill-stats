import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';

interface AlertNotification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  autoHide?: boolean;
  duration?: number;
}

interface UiState {
  drawerOpen: boolean;
  notificationsOpen: boolean;
  mobileMode: boolean;
  alertNotifications: AlertNotification[];
  isLoading: Record<string, boolean>;
}

const initialState: UiState = {
  drawerOpen: true,
  notificationsOpen: false,
  mobileMode: window.innerWidth < 768,
  alertNotifications: [],
  isLoading: {},
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setDrawerOpen: (state, action: PayloadAction<boolean>) => {
      state.drawerOpen = action.payload;
    },
    toggleDrawer: (state) => {
      state.drawerOpen = !state.drawerOpen;
    },
    setNotificationsOpen: (state, action: PayloadAction<boolean>) => {
      state.notificationsOpen = action.payload;
    },
    toggleNotifications: (state) => {
      state.notificationsOpen = !state.notificationsOpen;
    },
    setMobileMode: (state, action: PayloadAction<boolean>) => {
      state.mobileMode = action.payload;
      
      // Auto-close drawer in mobile mode
      if (action.payload) {
        state.drawerOpen = false;
      }
    },
    addAlert: (state, action: PayloadAction<AlertNotification>) => {
      state.alertNotifications.push(action.payload);
    },
    removeAlert: (state, action: PayloadAction<string>) => {
      state.alertNotifications = state.alertNotifications.filter(
        (alert) => alert.id !== action.payload
      );
    },
    clearAlerts: (state) => {
      state.alertNotifications = [];
    },
    setLoading: (state, action: PayloadAction<{ key: string; isLoading: boolean }>) => {
      state.isLoading[action.payload.key] = action.payload.isLoading;
    },
    clearLoadingState: (state) => {
      state.isLoading = {};
    },
  },
});

// Export actions
export const {
  setDrawerOpen,
  toggleDrawer,
  setNotificationsOpen,
  toggleNotifications,
  setMobileMode,
  addAlert,
  removeAlert,
  clearAlerts,
  setLoading,
  clearLoadingState,
} = uiSlice.actions;

// Export selectors
export const selectDrawerOpen = (state: RootState) => state.ui.drawerOpen;
export const selectNotificationsOpen = (state: RootState) => state.ui.notificationsOpen;
export const selectMobileMode = (state: RootState) => state.ui.mobileMode;
export const selectAlerts = (state: RootState) => state.ui.alertNotifications;
export const selectIsLoading = (state: RootState, key: string) => 
  state.ui.isLoading[key] || false;

// Helper function to generate unique IDs for alerts
export const generateAlertId = () => 
  `alert-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

export default uiSlice.reducer;
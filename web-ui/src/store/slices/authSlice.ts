import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { User, LoginCredentials, RegisterData } from '@/types';
import { api } from '../api';
import {
  setAuthData,
  clearAuthData,
  getToken,
  setupAxiosInterceptors,
  startTokenRefreshTimer
} from '@/utils/authUtils';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  authChecked: boolean;
  tokenRefreshTimer: NodeJS.Timeout | null;
}

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  loading: false,
  error: null,
  authChecked: false,
  tokenRefreshTimer: null,
};

// Async thunks
export const login = createAsyncThunk(
  'auth/login',
  async (credentials: LoginCredentials, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
        credentials: 'include',
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        return rejectWithValue(data.message || 'Login failed');
      }
      
      const { token, refreshToken, expiresIn, user } = data.data;
      
      // Setup auth data in storage
      setAuthData(token, refreshToken, expiresIn, user, credentials.rememberMe);
      
      // Set up token refresh and interceptors
      setupAxiosInterceptors();
      const refreshTimer = startTokenRefreshTimer();
      
      // Store the timer in the state
      dispatch(setTokenRefreshTimer(refreshTimer));
      
      // Invalidate user data to refetch
      dispatch(api.util.invalidateTags(['User']));
      
      return data.data;
    } catch (error) {
      return rejectWithValue((error as Error).message || 'Login failed');
    }
  }
);

export const register = createAsyncThunk(
  'auth/register',
  async (registerData: RegisterData, { rejectWithValue }) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registerData),
        credentials: 'include',
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        return rejectWithValue(data.message || 'Registration failed');
      }
      
      return data.data;
    } catch (error) {
      return rejectWithValue((error as Error).message || 'Registration failed');
    }
  }
);

export const logout = createAsyncThunk(
  'auth/logout',
  async (_, { dispatch, getState, rejectWithValue }) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      
      if (!response.ok) {
        const data = await response.json();
        return rejectWithValue(data.message || 'Logout failed');
      }
      
      // Clear the token refresh interval
      const state = getState() as RootState;
      const { tokenRefreshTimer } = state.auth;
      
      if (tokenRefreshTimer) {
        clearInterval(tokenRefreshTimer);
        dispatch(setTokenRefreshTimer(null));
      }
      
      // Clear auth data from storage
      clearAuthData();
      
      // Invalidate all cached data
      dispatch(api.util.resetApiState());
      
      return null;
    } catch (error) {
      return rejectWithValue((error as Error).message || 'Logout failed');
    }
  }
);

export const checkAuthStatus = createAsyncThunk(
  'auth/checkStatus',
  async (_, { dispatch, rejectWithValue }) => {
    try {
      // First check if we have a token in storage
      const token = getToken();
      
      if (!token) {
        // No token, user is not authenticated
        dispatch(setAuthChecked(true));
        return null;
      }
      
      // Set up axios interceptors for token handling
      setupAxiosInterceptors();
      
      // Check with server
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/user`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        // Token is invalid or session expired
        clearAuthData();
        return null;
      }
      
      const data = await response.json();
      
      // Start token refresh timer
      const refreshTimer = startTokenRefreshTimer();
      dispatch(setTokenRefreshTimer(refreshTimer));
      
      return data.data;
    } catch (error) {
      // Clear auth data on error
      clearAuthData();
      return rejectWithValue((error as Error).message || 'Authentication check failed');
    } finally {
      // Make sure we mark auth as checked regardless of outcome
      dispatch(setAuthChecked(true));
    }
  }
);

// Auth slice
const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setAuthChecked: (state, action: PayloadAction<boolean>) => {
      state.authChecked = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
    setTokenRefreshTimer: (state, action: PayloadAction<NodeJS.Timeout | null>) => {
      state.tokenRefreshTimer = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Login
      .addCase(login.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        state.isAuthenticated = true;
        state.user = action.payload;
        state.loading = false;
        state.error = null;
      })
      .addCase(login.rejected, (state, action) => {
        state.isAuthenticated = false;
        state.loading = false;
        state.error = action.payload as string;
      })
      
      // Register
      .addCase(register.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(register.fulfilled, (state, action) => {
        state.isAuthenticated = true;
        state.user = action.payload;
        state.loading = false;
        state.error = null;
      })
      .addCase(register.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      
      // Logout
      .addCase(logout.pending, (state) => {
        state.loading = true;
      })
      .addCase(logout.fulfilled, (state) => {
        state.isAuthenticated = false;
        state.user = null;
        state.loading = false;
        state.error = null;
      })
      .addCase(logout.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      
      // Check auth status
      .addCase(checkAuthStatus.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(checkAuthStatus.fulfilled, (state, action) => {
        state.loading = false;
        
        if (action.payload) {
          state.isAuthenticated = true;
          state.user = action.payload;
        } else {
          state.isAuthenticated = false;
          state.user = null;
        }
      })
      .addCase(checkAuthStatus.rejected, (state, action) => {
        state.isAuthenticated = false;
        state.user = null;
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

// Export actions
export const { setAuthChecked, clearError, setTokenRefreshTimer } = authSlice.actions;

// Export selectors
export const selectAuth = (state: RootState) => state.auth;
export const selectUser = (state: RootState) => state.auth.user;
export const selectIsAuthenticated = (state: RootState) => state.auth.isAuthenticated;
export const selectAuthLoading = (state: RootState) => state.auth.loading;
export const selectAuthError = (state: RootState) => state.auth.error;
export const selectAuthChecked = (state: RootState) => state.auth.authChecked;

export default authSlice.reducer;
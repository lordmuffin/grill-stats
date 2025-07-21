/**
 * Utility functions for authentication and session management
 */

import axios from 'axios';
import { store } from '@/store';
import { logout } from '@/store/slices/authSlice';

// Constants
const TOKEN_REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes
const TOKEN_EXPIRY_BUFFER = 60 * 1000; // 1 minute buffer before token expiry

// Session storage keys
export const TOKEN_KEY = 'auth_token';
export const REFRESH_TOKEN_KEY = 'refresh_token';
export const TOKEN_EXPIRY_KEY = 'token_expiry';
export const SESSION_USER_KEY = 'user_data';

// Get API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

/**
 * Get stored token from localStorage or sessionStorage based on "remember me" setting
 */
export const getToken = (): string | null => {
  const token = localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  return token;
};

/**
 * Get refresh token from localStorage or sessionStorage
 */
export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || sessionStorage.getItem(REFRESH_TOKEN_KEY);
};

/**
 * Get token expiry timestamp
 */
export const getTokenExpiry = (): number => {
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY) || sessionStorage.getItem(TOKEN_EXPIRY_KEY);
  return expiry ? parseInt(expiry, 10) : 0;
};

/**
 * Check if token is expired or about to expire
 */
export const isTokenExpired = (): boolean => {
  const expiry = getTokenExpiry();
  if (!expiry) return true;
  
  // Consider token expired if it's within the buffer time
  return Date.now() + TOKEN_EXPIRY_BUFFER >= expiry;
};

/**
 * Set authentication tokens and user data in storage
 */
export const setAuthData = (
  token: string, 
  refreshToken: string, 
  expiresIn: number, 
  userData: any, 
  rememberMe: boolean
): void => {
  // Calculate token expiry
  const expiryTime = Date.now() + expiresIn * 1000;
  
  // Store user data as JSON string
  const userStr = JSON.stringify(userData);
  
  // Store in appropriate storage based on "remember me" setting
  const storage = rememberMe ? localStorage : sessionStorage;
  
  storage.setItem(TOKEN_KEY, token);
  storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  storage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());
  storage.setItem(SESSION_USER_KEY, userStr);
};

/**
 * Clear auth data from both localStorage and sessionStorage
 */
export const clearAuthData = (): void => {
  // Clear from localStorage
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
  localStorage.removeItem(SESSION_USER_KEY);
  
  // Clear from sessionStorage
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_EXPIRY_KEY);
  sessionStorage.removeItem(SESSION_USER_KEY);
};

/**
 * Set up axios interceptor for adding auth token to requests
 */
export const setupAxiosInterceptors = (): void => {
  // Add token to all requests
  axios.interceptors.request.use(
    async (config) => {
      const token = getToken();
      
      if (token) {
        // Check if token is about to expire
        if (isTokenExpired()) {
          try {
            // Try to refresh the token
            const newToken = await refreshAuthToken();
            
            if (newToken) {
              config.headers.Authorization = `Bearer ${newToken}`;
            }
          } catch (error) {
            // If refresh fails, logout user
            store.dispatch(logout());
            return Promise.reject(error);
          }
        } else {
          // Token is still valid
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
      
      return config;
    },
    (error) => Promise.reject(error)
  );
  
  // Handle token expiration in responses
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;
      
      // If response status is 401 (Unauthorized) and we haven't tried to refresh the token yet
      if (
        error.response &&
        error.response.status === 401 &&
        !originalRequest._retry
      ) {
        originalRequest._retry = true;
        
        try {
          // Try to refresh the token
          const newToken = await refreshAuthToken();
          
          if (newToken) {
            // Update request header with new token
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            // Retry the original request
            return axios(originalRequest);
          }
        } catch (refreshError) {
          // If refresh fails, logout user
          store.dispatch(logout());
          return Promise.reject(refreshError);
        }
      }
      
      return Promise.reject(error);
    }
  );
};

/**
 * Set up token refresh timer
 */
export const startTokenRefreshTimer = (): NodeJS.Timeout => {
  return setInterval(async () => {
    if (getToken() && isTokenExpired()) {
      try {
        await refreshAuthToken();
      } catch (error) {
        console.error('Token refresh failed:', error);
        store.dispatch(logout());
      }
    }
  }, TOKEN_REFRESH_INTERVAL);
};

/**
 * Refresh the authentication token
 */
export const refreshAuthToken = async (): Promise<string | null> => {
  const refreshToken = getRefreshToken();
  
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }
  
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refreshToken,
    });
    
    if (response.data && response.data.data) {
      const { token, refreshToken: newRefreshToken, expiresIn } = response.data.data;
      
      // Determine if "remember me" was used by checking where the current refresh token is stored
      const rememberMe = !!localStorage.getItem(REFRESH_TOKEN_KEY);
      
      // Update storage with new tokens
      setAuthData(
        token,
        newRefreshToken,
        expiresIn,
        JSON.parse(localStorage.getItem(SESSION_USER_KEY) || sessionStorage.getItem(SESSION_USER_KEY) || '{}'),
        rememberMe
      );
      
      return token;
    }
    
    return null;
  } catch (error) {
    console.error('Token refresh failed:', error);
    clearAuthData();
    throw error;
  }
};

export default {
  getToken,
  getRefreshToken,
  getTokenExpiry,
  isTokenExpired,
  setAuthData,
  clearAuthData,
  setupAxiosInterceptors,
  startTokenRefreshTimer,
  refreshAuthToken,
};
import React, { createContext, useContext } from 'react';

const ApiContext = createContext();

export const useApi = () => {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error('useApi must be used within an ApiProvider');
  }
  return context;
};

export const ApiProvider = ({ children }) => {
  // Base URLs for different services
  const AUTH_BASE_URL = process.env.REACT_APP_AUTH_SERVICE_URL || 'http://localhost:8082';
  const DEVICE_BASE_URL = process.env.REACT_APP_DEVICE_SERVICE_URL || 'http://localhost:8080';
  const TEMP_BASE_URL = process.env.REACT_APP_TEMPERATURE_SERVICE_URL || 'http://localhost:8081';
  const HISTORICAL_BASE_URL = process.env.REACT_APP_HISTORICAL_SERVICE_URL || 'http://localhost:8083';

  const getBaseUrl = (endpoint) => {
    if (endpoint.startsWith('/api/auth')) {
      return AUTH_BASE_URL;
    } else if (endpoint.startsWith('/api/devices') && endpoint.includes('/history')) {
      return HISTORICAL_BASE_URL;
    } else if (endpoint.startsWith('/api/devices') || endpoint.startsWith('/api/sync')) {
      return DEVICE_BASE_URL;
    } else if (endpoint.startsWith('/api/temperature')) {
      return TEMP_BASE_URL;
    }
    return AUTH_BASE_URL; // Default
  };

  const apiCall = async (endpoint, options = {}) => {
    const baseUrl = getBaseUrl(endpoint);
    const url = `${baseUrl}${endpoint}`;
    
    // Add default headers
    const defaultHeaders = {
      'Content-Type': 'application/json',
    };

    // Add auth token if available and not already provided
    const token = localStorage.getItem('jwt_token');
    if (token && !options.headers?.Authorization) {
      defaultHeaders.Authorization = `Bearer ${token}`;
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      // If token is expired, redirect to login
      if (response.status === 401) {
        localStorage.removeItem('jwt_token');
        localStorage.removeItem('session_token');
        window.location.href = '/login';
      }
      
      return response;
    } catch (error) {
      console.error('API call failed:', error);
      throw error;
    }
  };

  const deviceApi = {
    getDevices: async (forceRefresh = false) => {
      const params = forceRefresh ? '?force_refresh=true' : '';
      return apiCall(`/api/devices${params}`);
    },
    
    getDevice: async (deviceId) => {
      return apiCall(`/api/devices/${deviceId}`);
    },
    
    getDeviceTemperature: async (deviceId, probeId = null) => {
      const params = probeId ? `?probe_id=${probeId}` : '';
      return apiCall(`/api/devices/${deviceId}/temperature${params}`);
    },
    
    getDeviceHistory: async (deviceId, options = {}) => {
      const params = new URLSearchParams();
      if (options.probeId) params.append('probe_id', options.probeId);
      if (options.startTime) params.append('start_time', options.startTime);
      if (options.endTime) params.append('end_time', options.endTime);
      if (options.limit) params.append('limit', options.limit);
      
      const queryString = params.toString();
      return apiCall(`/api/devices/${deviceId}/history${queryString ? `?${queryString}` : ''}`);
    },
    
    getDeviceHealth: async (deviceId) => {
      return apiCall(`/api/devices/${deviceId}/health`);
    },
    
    syncDevices: async () => {
      return apiCall('/api/sync', { method: 'POST' });
    },
    
    discoverDevices: async () => {
      return apiCall('/api/devices/discover', { method: 'POST' });
    },
    
    registerDevice: async (deviceId, nickname) => {
      return apiCall('/api/devices/register', {
        method: 'POST',
        body: JSON.stringify({ 
          device_id: deviceId, 
          nickname: nickname 
        }),
      });
    },
    
    removeDevice: async (deviceId) => {
      return apiCall(`/api/devices/${deviceId}`, { method: 'DELETE' });
    },
    
    getConfig: async () => {
      return apiCall('/api/config');
    }
  };

  const authApi = {
    login: async (email, password) => {
      return apiCall('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
    },
    
    register: async (email, password, name) => {
      return apiCall('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, name }),
      });
    },
    
    logout: async () => {
      return apiCall('/api/auth/logout', { method: 'POST' });
    },
    
    getStatus: async () => {
      return apiCall('/api/auth/status');
    },
    
    getCurrentUser: async () => {
      return apiCall('/api/auth/me');
    }
  };

  const thermoworksApi = {
    getAuthUrl: async () => {
      return apiCall('/api/auth/thermoworks');
    },
    
    getAuthStatus: async () => {
      return apiCall('/api/auth/thermoworks/status');
    },
    
    refreshToken: async () => {
      return apiCall('/api/auth/thermoworks/refresh', { method: 'POST' });
    }
  };

  const historicalApi = {
    getDeviceHistory: async (deviceId, options = {}) => {
      const params = new URLSearchParams();
      if (options.startTime) params.append('start_time', options.startTime);
      if (options.endTime) params.append('end_time', options.endTime);
      if (options.probeId) params.append('probe_id', options.probeId);
      if (options.aggregation) params.append('aggregation', options.aggregation);
      if (options.interval) params.append('interval', options.interval);
      if (options.limit) params.append('limit', options.limit);
      
      const queryString = params.toString();
      return apiCall(`/api/devices/${deviceId}/history${queryString ? `?${queryString}` : ''}`);
    },
    
    getDeviceStatistics: async (deviceId, options = {}) => {
      const params = new URLSearchParams();
      if (options.startTime) params.append('start_time', options.startTime);
      if (options.endTime) params.append('end_time', options.endTime);
      if (options.probeId) params.append('probe_id', options.probeId);
      
      const queryString = params.toString();
      return apiCall(`/api/devices/${deviceId}/statistics${queryString ? `?${queryString}` : ''}`);
    }
  };

  const value = {
    apiCall,
    deviceApi,
    authApi,
    thermoworksApi,
    historicalApi,
  };

  return (
    <ApiContext.Provider value={value}>
      {children}
    </ApiContext.Provider>
  );
};
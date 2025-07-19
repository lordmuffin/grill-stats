/**
 * API utilities for the grill-stats application
 *
 * This module provides functions to interact with the grill-stats backend services,
 * primarily for fetching temperature data from devices.
 */

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8080';
const AUTH_API_BASE_URL = process.env.REACT_APP_AUTH_API_BASE_URL || 'http://localhost:8082';

/**
 * Generic API request function with error handling
 *
 * @param {string} endpoint - API endpoint to request
 * @param {Object} options - Fetch options
 * @param {string} baseUrl - Base URL to use (defaults to API_BASE_URL)
 * @returns {Promise<any>} - Response data
 * @throws {Error} - Throws error on failed requests
 */
async function apiRequest(endpoint, options = {}, baseUrl = API_BASE_URL) {
  try {
    const url = `${baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      // Try to get error details from response
      let errorDetails = '';
      try {
        const errorData = await response.json();
        errorDetails = errorData.message || '';
      } catch (e) {
        // Ignore parsing errors
      }

      throw new Error(`API request failed (${response.status}): ${errorDetails}`);
    }

    // Check if the response is empty
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    }

    return {};
  } catch (error) {
    console.error(`API request error for ${endpoint}:`, error);
    throw error;
  }
}

/**
 * Make authenticated API request with JWT token
 *
 * @param {string} endpoint - API endpoint to request
 * @param {Object} options - Fetch options
 * @param {string} baseUrl - Base URL to use (defaults to API_BASE_URL)
 * @returns {Promise<any>} - Response data
 * @throws {Error} - Throws error on failed requests
 */
async function authenticatedApiRequest(endpoint, options = {}, baseUrl = API_BASE_URL) {
  const token = localStorage.getItem('jwt_token');
  const sessionToken = localStorage.getItem('session_token');

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (sessionToken) {
    headers['Session-Token'] = sessionToken;
  }

  return apiRequest(endpoint, { ...options, headers }, baseUrl);
}

/**
 * Get all available devices
 *
 * @param {boolean} forceRefresh - Whether to force a refresh from the API
 * @returns {Promise<Array>} - Array of device objects
 */
export async function getDevices(forceRefresh = false) {
  const response = await apiRequest(`/api/devices?force_refresh=${forceRefresh}`);
  return response.data?.devices || [];
}

/**
 * Get a specific device's details
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Device details
 */
export async function getDevice(deviceId) {
  const response = await apiRequest(`/api/devices/${deviceId}`);
  return response.data?.device;
}

/**
 * Get current temperature readings for a device
 *
 * @param {string} deviceId - Device ID
 * @param {string} probeId - Optional probe ID to filter results
 * @param {boolean} forceRefresh - Whether to force a refresh from the API
 * @returns {Promise<Array>} - Array of temperature reading objects
 */
export async function getCurrentTemperature(deviceId, probeId = null, forceRefresh = false) {
  let endpoint = `/api/devices/${deviceId}/temperature`;

  if (probeId) {
    endpoint += `?probe_id=${probeId}`;
    if (forceRefresh) {
      endpoint += '&force_refresh=true';
    }
  } else if (forceRefresh) {
    endpoint += '?force_refresh=true';
  }

  const response = await apiRequest(endpoint);
  return response.data?.readings || [];
}

/**
 * Get historical temperature readings for a device
 *
 * @param {string} deviceId - Device ID
 * @param {string} probeId - Optional probe ID to filter results
 * @param {string} startTime - Optional start time in ISO format
 * @param {string} endTime - Optional end time in ISO format
 * @param {number} limit - Maximum number of readings to return
 * @returns {Promise<Array>} - Array of temperature reading objects
 */
export async function getTemperatureHistory(deviceId, {
  probeId = null,
  startTime = null,
  endTime = null,
  limit = 100
} = {}) {
  let endpoint = `/api/devices/${deviceId}/history?limit=${limit}`;

  if (probeId) {
    endpoint += `&probe_id=${probeId}`;
  }

  if (startTime) {
    endpoint += `&start_time=${encodeURIComponent(startTime)}`;
  }

  if (endTime) {
    endpoint += `&end_time=${encodeURIComponent(endTime)}`;
  }

  const response = await apiRequest(endpoint);
  return response.data?.history || [];
}

/**
 * Get device health information
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Device health information
 */
export async function getDeviceHealth(deviceId) {
  const response = await apiRequest(`/api/devices/${deviceId}/health`);
  return response.data?.health;
}

/**
 * Get device health information (alias for getDeviceHealth)
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Device health information
 */
export async function getDeviceHealthStatus(deviceId) {
  return getDeviceHealth(deviceId);
}

/**
 * Set up a server-sent events connection for real-time temperature updates
 *
 * @param {string} deviceId - Device ID
 * @param {Function} onMessage - Callback function for temperature updates
 * @param {Function} onError - Callback function for errors
 * @returns {EventSource} - EventSource object that can be closed with .close()
 */
export function getTemperatureStream(deviceId, onMessage, onError) {
  try {
    const eventSource = new EventSource(`${API_BASE_URL}/api/temperature/stream/${deviceId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('Error parsing temperature stream data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Temperature stream error:', error);
      if (onError) {
        onError(error);
      }
    };

    return eventSource;
  } catch (error) {
    console.error('Failed to create temperature stream:', error);
    if (onError) {
      onError(error);
    }
    return null;
  }
}

/**
 * Manually trigger a data sync
 *
 * @returns {Promise<Object>} - Sync status
 */
export async function triggerSync() {
  return apiRequest('/api/sync', { method: 'POST' });
}

/**
 * Get recent temperature data for a device
 *
 * @param {string} deviceId - Device ID
 * @param {number} hours - Number of hours of data to retrieve
 * @returns {Promise<Array>} - Array of temperature reading objects
 */
export async function getRecentTemperatureData(deviceId, hours = 1) {
  const endTime = new Date().toISOString();
  const startTime = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();

  return getTemperatureHistory(deviceId, {
    startTime,
    endTime,
    limit: hours * 60 * 2, // Assuming readings every 30 seconds
  });
}

/**
 * Check connection status with the ThermoWorks API
 *
 * @returns {Promise<Object>} - Connection status
 */
export async function getThermoworksConnectionStatus() {
  const response = await apiRequest('/api/auth/thermoworks/status');
  return response.data;
}

/**
 * Discover devices from the ThermoWorks API
 *
 * @returns {Promise<Array>} - Array of discovered devices
 */
export async function discoverDevices() {
  const response = await apiRequest('/api/devices/discover', { method: 'POST' });
  return response.data?.devices || [];
}

// Authentication API functions

/**
 * Login user with email and password
 *
 * @param {Object} credentials - Login credentials
 * @param {string} credentials.email - User email
 * @param {string} credentials.password - User password
 * @param {string} credentials.login_type - Login type ('local' or 'thermoworks')
 * @returns {Promise<Object>} - Login response with tokens and user data
 */
export async function loginUser(credentials) {
  return apiRequest('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  }, AUTH_API_BASE_URL);
}

/**
 * Logout current user
 *
 * @returns {Promise<Object>} - Logout response
 */
export async function logoutUser() {
  return authenticatedApiRequest('/api/auth/logout', {
    method: 'POST',
  }, AUTH_API_BASE_URL);
}

/**
 * Register new user
 *
 * @param {Object} userData - User registration data
 * @param {string} userData.email - User email
 * @param {string} userData.password - User password
 * @param {string} userData.name - User name
 * @returns {Promise<Object>} - Registration response
 */
export async function registerUser(userData) {
  return apiRequest('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(userData),
  }, AUTH_API_BASE_URL);
}

/**
 * Check authentication status
 *
 * @param {string} token - JWT token to check
 * @returns {Promise<Object>} - Authentication status
 */
export async function checkAuthStatus(token) {
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return apiRequest('/api/auth/status', {
    method: 'GET',
    headers,
  }, AUTH_API_BASE_URL);
}

/**
 * Get current user information
 *
 * @returns {Promise<Object>} - Current user data
 */
export async function getCurrentUser() {
  return authenticatedApiRequest('/api/auth/me', {
    method: 'GET',
  }, AUTH_API_BASE_URL);
}

/**
 * Connect ThermoWorks account
 *
 * @param {Object} credentials - ThermoWorks credentials
 * @param {string} credentials.thermoworks_email - ThermoWorks email
 * @param {string} credentials.thermoworks_password - ThermoWorks password
 * @returns {Promise<Object>} - Connection response
 */
export async function connectThermoWorksAccount(credentials) {
  return authenticatedApiRequest('/api/auth/thermoworks/connect', {
    method: 'POST',
    body: JSON.stringify(credentials),
  }, AUTH_API_BASE_URL);
}

/**
 * Get user's active sessions
 *
 * @returns {Promise<Object>} - User sessions
 */
export async function getUserSessions() {
  return authenticatedApiRequest('/api/auth/sessions', {
    method: 'GET',
  }, AUTH_API_BASE_URL);
}

// Live Device Data API functions for User Story 3

/**
 * Get live device data including all channels and status
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Live device data
 */
export async function getLiveDeviceData(deviceId) {
  const response = await apiRequest(`/api/devices/${deviceId}/live`);
  return response.data;
}

/**
 * Get device channel configuration
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Device channel configuration
 */
export async function getDeviceChannels(deviceId) {
  const response = await apiRequest(`/api/devices/${deviceId}/channels`);
  return response.data;
}

/**
 * Get device status including battery, signal, and connection info
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Device status
 */
export async function getDeviceStatus(deviceId) {
  const response = await apiRequest(`/api/devices/${deviceId}/status`);
  return response.data;
}

/**
 * Set up a server-sent events connection for live device data updates
 *
 * @param {string} deviceId - Device ID
 * @param {Function} onMessage - Callback function for live data updates
 * @param {Function} onError - Callback function for errors
 * @param {Function} onOpen - Callback function when connection opens
 * @returns {EventSource} - EventSource object that can be closed with .close()
 */
export function getLiveDeviceDataStream(deviceId, onMessage, onError, onOpen) {
  try {
    const eventSource = new EventSource(`${API_BASE_URL}/api/devices/${deviceId}/stream`);

    eventSource.onopen = (event) => {
      console.log('Live device data stream connected');
      if (onOpen) {
        onOpen(event);
      }
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('Error parsing live device data:', error);
        if (onError) {
          onError(error);
        }
      }
    };

    eventSource.onerror = (error) => {
      console.error('Live device data stream error:', error);
      if (onError) {
        onError(error);
      }
    };

    return eventSource;
  } catch (error) {
    console.error('Failed to create live device data stream:', error);
    if (onError) {
      onError(error);
    }
    return null;
  }
}

/**
 * Get temperature alerts for a device
 *
 * @param {string} deviceId - Device ID
 * @param {Object} options - Query options
 * @param {string} options.startTime - Start time in ISO format
 * @param {string} options.endTime - End time in ISO format
 * @param {string} options.alertLevel - Alert level filter
 * @returns {Promise<Array>} - Array of temperature alerts
 */
export async function getTemperatureAlerts(deviceId, options = {}) {
  let endpoint = `/api/devices/${deviceId}/alerts`;

  const params = new URLSearchParams();
  if (options.startTime) params.append('start_time', options.startTime);
  if (options.endTime) params.append('end_time', options.endTime);
  if (options.alertLevel) params.append('alert_level', options.alertLevel);

  if (params.toString()) {
    endpoint += `?${params.toString()}`;
  }

  const response = await apiRequest(endpoint);
  return response.data?.alerts || [];
}

/**
 * Acknowledge a temperature alert
 *
 * @param {string} deviceId - Device ID
 * @param {number} alertId - Alert ID
 * @returns {Promise<Object>} - Acknowledgment response
 */
export async function acknowledgeTemperatureAlert(deviceId, alertId) {
  return apiRequest(`/api/devices/${deviceId}/alerts/${alertId}/acknowledge`, {
    method: 'POST'
  });
}

/**
 * Get device summary with live status
 *
 * @param {string} deviceId - Device ID
 * @returns {Promise<Object>} - Device summary with live status
 */
export async function getDeviceSummary(deviceId) {
  const response = await apiRequest(`/api/devices/${deviceId}/summary`);
  return response.data;
}

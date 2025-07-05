/**
 * API utilities for the grill-stats application
 * 
 * This module provides functions to interact with the grill-stats backend services,
 * primarily for fetching temperature data from devices.
 */

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8080';

/**
 * Generic API request function with error handling
 * 
 * @param {string} endpoint - API endpoint to request
 * @param {Object} options - Fetch options
 * @returns {Promise<any>} - Response data
 * @throws {Error} - Throws error on failed requests
 */
async function apiRequest(endpoint, options = {}) {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
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
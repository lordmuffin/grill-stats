import React, { useState, useEffect } from 'react';
import RealTimeChart from './RealTimeChart';
import { getDevices, triggerSync } from '../utils/api';
import './TemperatureDashboard.css';

/**
 * Temperature Dashboard component that allows selecting devices and
 * configuring the real-time chart display
 */
const TemperatureDashboard = () => {
  // Device selection state
  const [devices, setDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Chart configuration state
  const [refreshInterval, setRefreshInterval] = useState(10000); // 10 seconds
  const [historyHours, setHistoryHours] = useState(1); // 1 hour
  
  // Load devices on component mount
  useEffect(() => {
    loadDevices();
  }, []);
  
  // Function to load devices
  const loadDevices = async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    
    try {
      const deviceList = await getDevices(forceRefresh);
      
      setDevices(deviceList);
      
      // If there are devices and none is selected yet, select the first one
      if (deviceList.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(deviceList[0].device_id);
      }
      
      setLoading(false);
    } catch (err) {
      console.error('Error loading devices:', err);
      setError('Failed to load devices. Please try again.');
      setLoading(false);
    }
  };
  
  // Function to manually sync data
  const handleSync = async () => {
    try {
      await triggerSync();
      // Refresh device list
      loadDevices(true);
    } catch (err) {
      console.error('Error syncing data:', err);
      setError('Failed to sync data. Please try again.');
    }
  };
  
  // Handle device selection change
  const handleDeviceChange = (event) => {
    setSelectedDeviceId(event.target.value);
  };
  
  // Handle refresh interval change
  const handleRefreshIntervalChange = (event) => {
    setRefreshInterval(parseInt(event.target.value, 10));
  };
  
  // Handle history hours change
  const handleHistoryHoursChange = (event) => {
    setHistoryHours(parseInt(event.target.value, 10));
  };
  
  // Render loading state
  if (loading) {
    return (
      <div className="temperature-dashboard loading-state">
        <div className="spinner"></div>
        <p>Loading devices...</p>
      </div>
    );
  }
  
  // Render error state
  if (error) {
    return (
      <div className="temperature-dashboard error-state">
        <h3>Error</h3>
        <p>{error}</p>
        <button onClick={() => loadDevices()}>Retry</button>
      </div>
    );
  }
  
  // Render no devices state
  if (devices.length === 0) {
    return (
      <div className="temperature-dashboard empty-state">
        <h2>No temperature devices found</h2>
        <p>No devices were found in your account.</p>
        <button onClick={handleSync}>Sync Devices</button>
      </div>
    );
  }
  
  // Find the selected device name
  const selectedDevice = devices.find(device => device.device_id === selectedDeviceId);
  const deviceName = selectedDevice ? selectedDevice.name : 'Unknown Device';
  
  // Render dashboard with devices
  return (
    <div className="temperature-dashboard">
      <div className="dashboard-header">
        <h2>Temperature Monitor</h2>
        
        <div className="dashboard-controls">
          {/* Device selection */}
          <div className="control-group">
            <label htmlFor="device-select">Device:</label>
            <select
              id="device-select"
              value={selectedDeviceId}
              onChange={handleDeviceChange}
            >
              {devices.map(device => (
                <option key={device.device_id} value={device.device_id}>
                  {device.name}
                </option>
              ))}
            </select>
          </div>
          
          {/* Refresh interval selection */}
          <div className="control-group">
            <label htmlFor="refresh-interval">Refresh Every:</label>
            <select
              id="refresh-interval"
              value={refreshInterval}
              onChange={handleRefreshIntervalChange}
            >
              <option value={5000}>5 seconds</option>
              <option value={10000}>10 seconds</option>
              <option value={30000}>30 seconds</option>
              <option value={60000}>1 minute</option>
            </select>
          </div>
          
          {/* History duration selection */}
          <div className="control-group">
            <label htmlFor="history-hours">History:</label>
            <select
              id="history-hours"
              value={historyHours}
              onChange={handleHistoryHoursChange}
            >
              <option value={0.5}>30 minutes</option>
              <option value={1}>1 hour</option>
              <option value={3}>3 hours</option>
              <option value={6}>6 hours</option>
              <option value={12}>12 hours</option>
              <option value={24}>24 hours</option>
            </select>
          </div>
          
          {/* Sync button */}
          <button className="sync-button" onClick={handleSync}>
            Sync Now
          </button>
        </div>
      </div>
      
      {/* Real-time chart */}
      <RealTimeChart
        deviceId={selectedDeviceId}
        refreshInterval={refreshInterval}
        historyHours={historyHours}
        height={500}
        title={`${deviceName} Temperature`}
      />
      
      <div className="dashboard-footer">
        <p>
          <span className="info-icon">ℹ️</span>
          The chart updates every {refreshInterval / 1000} seconds and shows the last {historyHours} hour(s) of data.
          Disconnected probes will be indicated in the chart area.
        </p>
      </div>
    </div>
  );
};

export default TemperatureDashboard;
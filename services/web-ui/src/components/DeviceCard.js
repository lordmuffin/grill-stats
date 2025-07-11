import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../contexts/ApiContext';

const DeviceCard = ({ device, onRefresh }) => {
  const [loadingTemp, setLoadingTemp] = useState(false);
  const [temperature, setTemperature] = useState(null);
  const [tempError, setTempError] = useState(null);
  const { deviceApi } = useApi();
  const navigate = useNavigate();

  const getStatusColor = (status) => {
    switch (status) {
      case 'online':
        return 'status-online';
      case 'offline':
        return 'status-offline';
      case 'idle':
        return 'status-idle';
      default:
        return 'status-offline';
    }
  };

  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return 'Never';
    
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  const formatTemperature = (temp, unit = 'F') => {
    if (temp === null || temp === undefined) return '--';
    return `${Math.round(temp)}°${unit}`;
  };

  const getBatteryLevel = () => {
    if (device.battery_level === null || device.battery_level === undefined) {
      return 'Unknown';
    }
    return `${device.battery_level}%`;
  };

  const getSignalStrength = () => {
    if (device.signal_strength === null || device.signal_strength === undefined) {
      return 'Unknown';
    }
    return `${device.signal_strength}%`;
  };

  const handleGetTemperature = async () => {
    try {
      setLoadingTemp(true);
      setTempError(null);
      
      const response = await deviceApi.getDeviceTemperature(device.device_id);
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        setTemperature(data.data.readings || []);
      } else {
        setTempError(data.message || 'Failed to get temperature');
      }
    } catch (err) {
      setTempError('Network error getting temperature');
      console.error('Error getting temperature:', err);
    } finally {
      setLoadingTemp(false);
    }
  };

  const handleViewHistory = () => {
    navigate(`/devices/${device.device_id}/history`);
  };

  const handleLiveView = () => {
    navigate(`/devices/${device.device_id}/live`);
  };

  return (
    <div className="device-card">
      <h3>{device.name}</h3>
      <div className="device-model">{device.model}</div>
      
      <div className="device-status">
        <span className={`status-indicator ${getStatusColor(device.status)}`}></span>
        <span style={{ textTransform: 'capitalize' }}>{device.status}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#95a5a6' }}>
          {formatLastSeen(device.last_seen)}
        </span>
      </div>
      
      <div className="device-details">
        <div className="detail-item">
          <span>Battery:</span>
          <span>{getBatteryLevel()}</span>
        </div>
        <div className="detail-item">
          <span>Signal:</span>
          <span>{getSignalStrength()}</span>
        </div>
        <div className="detail-item">
          <span>Type:</span>
          <span style={{ textTransform: 'capitalize' }}>{device.device_type}</span>
        </div>
        <div className="detail-item">
          <span>Probes:</span>
          <span>{device.probes ? device.probes.length : 0}</span>
        </div>
      </div>
      
      {temperature && temperature.length > 0 && (
        <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#2c3e50' }}>
            Current Temperatures:
          </h4>
          {temperature.map((reading, index) => (
            <div key={index} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span>Probe {reading.probe_id}:</span>
              <span style={{ fontWeight: 'bold' }}>
                {formatTemperature(reading.temperature, reading.unit)}
              </span>
            </div>
          ))}
        </div>
      )}
      
      {tempError && (
        <div style={{ marginTop: '1rem', color: '#e74c3c', fontSize: '0.8rem' }}>
          {tempError}
        </div>
      )}
      
      <div className="device-actions">
        <button 
          onClick={handleLiveView}
          className="btn btn-primary btn-small"
          title="View live temperature monitoring dashboard"
        >
          Live View
        </button>
        <button 
          onClick={handleGetTemperature}
          className="btn btn-secondary btn-small"
          disabled={loadingTemp}
        >
          {loadingTemp ? 'Loading...' : 'Get Temp'}
        </button>
        <button 
          onClick={handleViewHistory}
          className="btn btn-secondary btn-small"
        >
          History
        </button>
      </div>
      
      {device.firmware_version && (
        <div style={{ 
          marginTop: '1rem', 
          fontSize: '0.7rem', 
          color: '#95a5a6',
          borderTop: '1px solid #ecf0f1',
          paddingTop: '0.5rem'
        }}>
          Firmware: {device.firmware_version}
        </div>
      )}
    </div>
  );
};

export default DeviceCard;
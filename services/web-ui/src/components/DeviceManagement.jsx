import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../contexts/ApiContext';
import AddDeviceForm from './AddDeviceForm';
import RemoveDeviceDialog from './RemoveDeviceDialog';
import './DeviceManagement.css';

const DeviceManagement = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isFormExpanded, setIsFormExpanded] = useState(false);
  const [removeDialog, setRemoveDialog] = useState({ isOpen: false, device: null });
  const [mockMode, setMockMode] = useState(false);
  const { deviceApi } = useApi();
  const navigate = useNavigate();

  useEffect(() => {
    fetchDevices();
    checkMockMode();
  }, []);

  const checkMockMode = async () => {
    try {
      const response = await deviceApi.getConfig();
      const data = await response.json();
      if (response.ok) {
        setMockMode(data.mock_mode || false);
      }
    } catch (error) {
      console.error('Error checking mock mode:', error);
    }
  };

  const fetchDevices = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await deviceApi.getDevices(forceRefresh);
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        setDevices(data.data.devices || []);
      } else {
        setError(data.message || 'Failed to fetch devices');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error('Error fetching devices:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeviceAdded = (newDevice) => {
    // Refresh the device list to show the newly added device
    fetchDevices(true);
  };

  const handleDeviceRemoved = (removedDevice) => {
    // Remove the device from the local state
    setDevices(prev => prev.filter(device => device.device_id !== removedDevice.device_id));
    setRemoveDialog({ isOpen: false, device: null });
  };

  const handleRemoveDevice = (device) => {
    setRemoveDialog({ isOpen: true, device });
  };

  const handleSync = async () => {
    try {
      setError(null);
      const response = await deviceApi.syncDevices();
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        // Refresh devices after sync
        setTimeout(() => {
          fetchDevices(true);
        }, 2000);
      } else {
        setError(data.message || 'Sync failed');
      }
    } catch (err) {
      setError('Network error during sync. Please try again.');
      console.error('Error syncing devices:', err);
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

  if (loading) {
    return (
      <div className="device-management">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading devices...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="device-management">
      <div className="device-management-header">
        <h1 className="device-management-title">Device Management</h1>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {mockMode && (
            <div className="mock-mode-indicator">
              Mock Mode
            </div>
          )}
          
          <div className="device-management-actions">
            <button 
              onClick={() => fetchDevices(true)} 
              className="btn btn-secondary"
              disabled={loading}
            >
              Refresh
            </button>
            <button 
              onClick={handleSync} 
              className="btn btn-primary"
            >
              Sync with ThermoWorks
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="message message-error">
          {error}
        </div>
      )}

      <AddDeviceForm
        isExpanded={isFormExpanded}
        onToggle={() => setIsFormExpanded(!isFormExpanded)}
        onDeviceAdded={handleDeviceAdded}
      />

      <div className="device-list-container">
        <div className="device-list-header">
          <h2 className="device-list-title">Your Devices</h2>
          <span className="device-count">
            {devices.length} device{devices.length !== 1 ? 's' : ''}
          </span>
        </div>
        
        {devices.length === 0 ? (
          <div className="empty-state">
            <h3>No devices registered</h3>
            <p>
              You haven't registered any ThermoWorks devices yet.<br />
              Use the form above to add your first device, or sync with your ThermoWorks account to discover devices.
            </p>
            <button 
              onClick={() => setIsFormExpanded(true)}
              className="btn btn-primary"
            >
              Add Your First Device
            </button>
          </div>
        ) : (
          <div className="device-grid">
            {devices.map(device => (
              <DeviceCard 
                key={device.device_id}
                device={device}
                onRemove={handleRemoveDevice}
                onNavigate={navigate}
                formatLastSeen={formatLastSeen}
                getStatusColor={getStatusColor}
              />
            ))}
          </div>
        )}
      </div>

      <RemoveDeviceDialog
        device={removeDialog.device}
        isOpen={removeDialog.isOpen}
        onClose={() => setRemoveDialog({ isOpen: false, device: null })}
        onDeviceRemoved={handleDeviceRemoved}
      />
    </div>
  );
};

// Enhanced DeviceCard component with remove functionality
const DeviceCard = ({ device, onRemove, onNavigate, formatLastSeen, getStatusColor }) => {
  const deviceName = device.name || device.nickname || `Device ${device.device_id}`;
  
  return (
    <div className="device-card">
      <div className="device-card-header">
        <div className="device-info">
          <h3 className="device-name">{deviceName}</h3>
          <div className="device-id">{device.device_id}</div>
        </div>
        <button
          onClick={() => onRemove(device)}
          className="device-remove-btn"
          title="Remove device"
        >
          Remove
        </button>
      </div>
      
      <div className="device-status">
        <span className={`status-indicator ${getStatusColor(device.status)}`}></span>
        <span style={{ textTransform: 'capitalize' }}>{device.status || 'Unknown'}</span>
        <span className="device-last-seen">
          {formatLastSeen(device.last_seen)}
        </span>
      </div>
      
      {device.model && (
        <div style={{ marginBottom: '1rem', color: '#7f8c8d', fontSize: '0.9rem' }}>
          Model: {device.model}
        </div>
      )}
      
      {device.device_type && (
        <div style={{ marginBottom: '1rem', color: '#7f8c8d', fontSize: '0.9rem' }}>
          Type: <span style={{ textTransform: 'capitalize' }}>{device.device_type}</span>
        </div>
      )}
      
      {device.probes && device.probes.length > 0 && (
        <div style={{ marginBottom: '1rem', color: '#7f8c8d', fontSize: '0.9rem' }}>
          Probes: {device.probes.length}
        </div>
      )}
      
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <button
          onClick={() => onNavigate(`/devices/${device.device_id}/live`)}
          className="btn btn-primary"
          style={{ flex: 1, fontSize: '0.85rem', padding: '0.5rem' }}
        >
          Live View
        </button>
        <button
          onClick={() => onNavigate(`/devices/${device.device_id}/history`)}
          className="btn btn-secondary"
          style={{ flex: 1, fontSize: '0.85rem', padding: '0.5rem' }}
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

export default DeviceManagement;
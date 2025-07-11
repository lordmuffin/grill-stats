import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../contexts/ApiContext';
import DeviceCard from './DeviceCard';

const DeviceList = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const { deviceApi } = useApi();
  const navigate = useNavigate();

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

  const handleSync = async () => {
    try {
      setSyncing(true);
      setError(null);
      
      const response = await deviceApi.syncDevices();
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        // Wait a moment for sync to complete, then refresh
        setTimeout(() => {
          fetchDevices(true);
        }, 2000);
      } else {
        setError(data.message || 'Sync failed');
      }
    } catch (err) {
      setError('Network error during sync. Please try again.');
      console.error('Error syncing devices:', err);
    } finally {
      setSyncing(false);
    }
  };

  const handleRefresh = () => {
    fetchDevices(true);
  };

  useEffect(() => {
    fetchDevices();
  }, []);

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

  if (loading) {
    return (
      <div className="main-content">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading devices...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      <div className="device-list">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2>Your Devices</h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button 
              onClick={() => navigate('/devices/manage')}
              className="btn btn-primary"
            >
              Manage Devices
            </button>
            <button 
              onClick={handleRefresh} 
              className="btn btn-secondary"
              disabled={loading}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
            <button 
              onClick={handleSync} 
              className="btn btn-secondary"
              disabled={syncing}
            >
              {syncing ? 'Syncing...' : 'Sync with ThermoWorks'}
            </button>
          </div>
        </div>
        
        {error && (
          <div className="error-message" style={{ marginBottom: '1rem' }}>
            {error}
          </div>
        )}
        
        {devices.length === 0 ? (
          <div className="empty-state">
            <h3>No devices found</h3>
            <p>
              You don't have any ThermoWorks devices connected yet. 
              <br />
              Use Device Management to add devices manually or sync with your ThermoWorks account.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <button 
                onClick={() => navigate('/devices/manage')}
                className="btn btn-primary"
              >
                Manage Devices
              </button>
              <button 
                onClick={handleSync} 
                className="btn btn-secondary"
                disabled={syncing}
              >
                {syncing ? 'Syncing...' : 'Sync with ThermoWorks'}
              </button>
            </div>
          </div>
        ) : (
          <div className="device-grid">
            {devices.map(device => (
              <DeviceCard 
                key={device.device_id} 
                device={device}
                onRefresh={() => fetchDevices(true)}
              />
            ))}
          </div>
        )}
        
        {devices.length > 0 && (
          <div style={{ marginTop: '2rem', textAlign: 'center', color: '#7f8c8d' }}>
            <p>
              Showing {devices.length} device{devices.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DeviceList;
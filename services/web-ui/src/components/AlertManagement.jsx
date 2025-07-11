import React, { useState, useEffect } from 'react';
import SetAlertForm from './SetAlertForm';
import './AlertManagement.css';

const AlertManagement = ({ devices = [], probes = [] }) => {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingAlert, setEditingAlert] = useState(null);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [selectedProbe, setSelectedProbe] = useState('');
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchAlerts();
    }, []);

    const fetchAlerts = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/alerts', {
                credentials: 'include'
            });
            const data = await response.json();
            
            if (data.success) {
                setAlerts(data.data.alerts || []);
            } else {
                setError(data.message || 'Failed to fetch alerts');
            }
        } catch (error) {
            console.error('Error fetching alerts:', error);
            setError('Network error occurred');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateAlert = () => {
        if (!selectedDevice || !selectedProbe) {
            alert('Please select a device and probe first');
            return;
        }
        
        setEditingAlert(null);
        setShowForm(true);
    };

    const handleEditAlert = (alert) => {
        setEditingAlert(alert);
        setSelectedDevice(alert.device_id);
        setSelectedProbe(alert.probe_id);
        setShowForm(true);
    };

    const handleSaveAlert = (alertData) => {
        if (editingAlert) {
            // Update existing alert in list
            setAlerts(prev => prev.map(alert => 
                alert.id === alertData.id ? alertData : alert
            ));
        } else {
            // Add new alert to list
            setAlerts(prev => [...prev, alertData]);
        }
        
        setShowForm(false);
        setEditingAlert(null);
        setSelectedDevice('');
        setSelectedProbe('');
    };

    const handleDeleteAlert = (alertId) => {
        setAlerts(prev => prev.filter(alert => alert.id !== alertId));
        setShowForm(false);
        setEditingAlert(null);
    };

    const handleCancelForm = () => {
        setShowForm(false);
        setEditingAlert(null);
        if (!editingAlert) {
            setSelectedDevice('');
            setSelectedProbe('');
        }
    };

    const getDeviceName = (deviceId) => {
        const device = devices.find(d => d.id === deviceId);
        return device ? device.name : deviceId;
    };

    const getProbeName = (deviceId, probeId) => {
        const device = devices.find(d => d.id === deviceId);
        if (device && device.probes) {
            const probe = device.probes.find(p => p.id === probeId);
            return probe ? probe.name : probeId;
        }
        return probeId;
    };

    const getAlertTypeIcon = (alertType) => {
        switch (alertType) {
            case 'target': return '🎯';
            case 'range': return '📊';
            case 'rising': return '📈';
            case 'falling': return '📉';
            default: return '🚨';
        }
    };

    const getAlertStatusBadge = (alert) => {
        if (!alert.is_active) {
            return <span className="alert-status inactive">Inactive</span>;
        }
        
        if (alert.triggered_at && !alert.notification_sent) {
            return <span className="alert-status triggered">Triggered</span>;
        }
        
        return <span className="alert-status active">Active</span>;
    };

    const formatTemperature = (temp, unit = 'F') => {
        return temp !== null && temp !== undefined ? `${temp}°${unit}` : 'N/A';
    };

    const getAlertDescription = (alert) => {
        switch (alert.alert_type) {
            case 'target':
                return `Target: ${formatTemperature(alert.target_temperature, alert.temperature_unit)}`;
            case 'range':
                return `Range: ${formatTemperature(alert.min_temperature, alert.temperature_unit)} - ${formatTemperature(alert.max_temperature, alert.temperature_unit)}`;
            case 'rising':
                return `Rise by: ${formatTemperature(alert.threshold_value, alert.temperature_unit)}`;
            case 'falling':
                return `Drop by: ${formatTemperature(alert.threshold_value, alert.temperature_unit)}`;
            default:
                return '';
        }
    };

    if (loading) {
        return (
            <div className="alert-management">
                <div className="loading-state">
                    <div className="loading-spinner"></div>
                    <p>Loading alerts...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="alert-management">
                <div className="error-state">
                    <p>Error: {error}</p>
                    <button onClick={fetchAlerts} className="btn btn-primary">
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    if (showForm) {
        return (
            <div className="alert-management">
                <SetAlertForm
                    deviceId={selectedDevice}
                    probeId={selectedProbe}
                    deviceName={getDeviceName(selectedDevice)}
                    probeName={getProbeName(selectedDevice, selectedProbe)}
                    existingAlert={editingAlert}
                    onSave={handleSaveAlert}
                    onCancel={handleCancelForm}
                    onDelete={handleDeleteAlert}
                />
            </div>
        );
    }

    return (
        <div className="alert-management">
            <div className="alert-management-header">
                <h2>Temperature Alerts</h2>
                <p className="alert-count">{alerts.length} alert{alerts.length !== 1 ? 's' : ''} configured</p>
            </div>

            <div className="alert-creation-section">
                <h3>Create New Alert</h3>
                <div className="device-probe-selector">
                    <div className="selector-group">
                        <label htmlFor="device-select">Device:</label>
                        <select
                            id="device-select"
                            value={selectedDevice}
                            onChange={(e) => {
                                setSelectedDevice(e.target.value);
                                setSelectedProbe(''); // Reset probe selection
                            }}
                        >
                            <option value="">Select a device...</option>
                            {devices.map(device => (
                                <option key={device.id} value={device.id}>
                                    {device.name || device.id}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="selector-group">
                        <label htmlFor="probe-select">Probe:</label>
                        <select
                            id="probe-select"
                            value={selectedProbe}
                            onChange={(e) => setSelectedProbe(e.target.value)}
                            disabled={!selectedDevice}
                        >
                            <option value="">Select a probe...</option>
                            {selectedDevice && devices
                                .find(d => d.id === selectedDevice)?.probes?.map(probe => (
                                <option key={probe.id} value={probe.id}>
                                    {probe.name || probe.id}
                                </option>
                            ))}
                        </select>
                    </div>

                    <button
                        onClick={handleCreateAlert}
                        className="btn btn-primary"
                        disabled={!selectedDevice || !selectedProbe}
                    >
                        Create Alert
                    </button>
                </div>
            </div>

            <div className="alerts-list">
                <h3>Existing Alerts</h3>
                
                {alerts.length === 0 ? (
                    <div className="empty-state">
                        <p>No alerts configured yet.</p>
                        <p>Create your first alert above to start monitoring temperatures!</p>
                    </div>
                ) : (
                    <div className="alerts-grid">
                        {alerts.map(alert => (
                            <div key={alert.id} className="alert-card">
                                <div className="alert-card-header">
                                    <div className="alert-icon">
                                        {getAlertTypeIcon(alert.alert_type)}
                                    </div>
                                    <div className="alert-title">
                                        <h4>{alert.name}</h4>
                                        {getAlertStatusBadge(alert)}
                                    </div>
                                </div>

                                <div className="alert-card-body">
                                    <div className="alert-device-info">
                                        <span className="device-name">
                                            {getDeviceName(alert.device_id)}
                                        </span>
                                        <span className="probe-name">
                                            {getProbeName(alert.device_id, alert.probe_id)}
                                        </span>
                                    </div>

                                    <div className="alert-config">
                                        <span className="alert-type-label">
                                            {alert.alert_type.charAt(0).toUpperCase() + alert.alert_type.slice(1)} Alert
                                        </span>
                                        <span className="alert-description">
                                            {getAlertDescription(alert)}
                                        </span>
                                    </div>

                                    {alert.description && (
                                        <div className="alert-user-description">
                                            {alert.description}
                                        </div>
                                    )}

                                    {alert.triggered_at && (
                                        <div className="alert-last-triggered">
                                            Last triggered: {new Date(alert.triggered_at).toLocaleString()}
                                        </div>
                                    )}
                                </div>

                                <div className="alert-card-actions">
                                    <button
                                        onClick={() => handleEditAlert(alert)}
                                        className="btn btn-secondary btn-sm"
                                    >
                                        Edit
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AlertManagement;
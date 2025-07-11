import React, { useState, useEffect } from 'react';
import './SetAlertForm.css';

const SetAlertForm = ({ 
    deviceId, 
    probeId, 
    deviceName, 
    probeName,
    existingAlert = null,
    onSave,
    onCancel,
    onDelete
}) => {
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        alert_type: 'target',
        target_temperature: '',
        min_temperature: '',
        max_temperature: '',
        threshold_value: '',
        temperature_unit: 'F'
    });
    
    const [alertTypes, setAlertTypes] = useState([]);
    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);

    // Load alert types on component mount
    useEffect(() => {
        const fetchAlertTypes = async () => {
            try {
                const response = await fetch('/api/alerts/types', {
                    credentials: 'include'
                });
                const data = await response.json();
                
                if (data.success) {
                    setAlertTypes(data.data.alert_types);
                }
            } catch (error) {
                console.error('Error fetching alert types:', error);
            }
        };
        
        fetchAlertTypes();
    }, []);

    // Populate form with existing alert data
    useEffect(() => {
        if (existingAlert) {
            setFormData({
                name: existingAlert.name || '',
                description: existingAlert.description || '',
                alert_type: existingAlert.alert_type || 'target',
                target_temperature: existingAlert.target_temperature || '',
                min_temperature: existingAlert.min_temperature || '',
                max_temperature: existingAlert.max_temperature || '',
                threshold_value: existingAlert.threshold_value || '',
                temperature_unit: existingAlert.temperature_unit || 'F'
            });
        } else {
            // Set default name for new alerts
            setFormData(prev => ({
                ...prev,
                name: `${deviceName || deviceId} ${probeName || probeId} Alert`
            }));
        }
    }, [existingAlert, deviceId, probeId, deviceName, probeName]);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
        
        // Clear error for this field
        if (errors[name]) {
            setErrors(prev => ({
                ...prev,
                [name]: null
            }));
        }
    };

    const validateForm = () => {
        const newErrors = {};
        
        if (!formData.name.trim()) {
            newErrors.name = 'Alert name is required';
        }
        
        switch (formData.alert_type) {
            case 'target':
                if (!formData.target_temperature || isNaN(formData.target_temperature)) {
                    newErrors.target_temperature = 'Valid target temperature is required';
                }
                break;
                
            case 'range':
                if (!formData.min_temperature || isNaN(formData.min_temperature)) {
                    newErrors.min_temperature = 'Valid minimum temperature is required';
                }
                if (!formData.max_temperature || isNaN(formData.max_temperature)) {
                    newErrors.max_temperature = 'Valid maximum temperature is required';
                }
                if (formData.min_temperature && formData.max_temperature && 
                    parseFloat(formData.min_temperature) >= parseFloat(formData.max_temperature)) {
                    newErrors.max_temperature = 'Maximum must be greater than minimum';
                }
                break;
                
            case 'rising':
            case 'falling':
                if (!formData.threshold_value || isNaN(formData.threshold_value) || 
                    parseFloat(formData.threshold_value) <= 0) {
                    newErrors.threshold_value = 'Valid positive threshold value is required';
                }
                break;
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!validateForm()) {
            return;
        }
        
        setSaving(true);
        
        try {
            const alertData = {
                device_id: deviceId,
                probe_id: probeId,
                ...formData,
                // Convert string numbers to actual numbers
                target_temperature: formData.target_temperature ? parseFloat(formData.target_temperature) : null,
                min_temperature: formData.min_temperature ? parseFloat(formData.min_temperature) : null,
                max_temperature: formData.max_temperature ? parseFloat(formData.max_temperature) : null,
                threshold_value: formData.threshold_value ? parseFloat(formData.threshold_value) : null
            };
            
            let response;
            if (existingAlert) {
                // Update existing alert
                response = await fetch(`/api/alerts/${existingAlert.id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify(alertData)
                });
            } else {
                // Create new alert
                response = await fetch('/api/alerts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify(alertData)
                });
            }
            
            const data = await response.json();
            
            if (data.success) {
                onSave && onSave(data.data);
            } else {
                if (data.errors) {
                    setErrors(data.errors.reduce((acc, error) => ({ ...acc, [error]: error }), {}));
                } else {
                    setErrors({ general: data.message || 'Failed to save alert' });
                }
            }
        } catch (error) {
            console.error('Error saving alert:', error);
            setErrors({ general: 'Network error occurred' });
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!existingAlert || !window.confirm('Are you sure you want to delete this alert?')) {
            return;
        }
        
        setSaving(true);
        
        try {
            const response = await fetch(`/api/alerts/${existingAlert.id}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            
            const data = await response.json();
            
            if (data.success) {
                onDelete && onDelete(existingAlert.id);
            } else {
                setErrors({ general: data.message || 'Failed to delete alert' });
            }
        } catch (error) {
            console.error('Error deleting alert:', error);
            setErrors({ general: 'Network error occurred' });
        } finally {
            setSaving(false);
        }
    };

    const currentAlertType = alertTypes.find(type => type.value === formData.alert_type);

    return (
        <div className="alert-form-container">
            <div className="alert-form-header">
                <h3>{existingAlert ? 'Edit Alert' : 'Create New Alert'}</h3>
                <p className="alert-form-subtitle">
                    {deviceName || deviceId} - {probeName || probeId}
                </p>
            </div>
            
            <form onSubmit={handleSubmit} className="alert-form">
                {errors.general && (
                    <div className="alert-form-error general-error">
                        {errors.general}
                    </div>
                )}
                
                <div className="form-group">
                    <label htmlFor="name">Alert Name *</label>
                    <input
                        type="text"
                        id="name"
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        className={errors.name ? 'error' : ''}
                        placeholder="Enter alert name"
                    />
                    {errors.name && <div className="field-error">{errors.name}</div>}
                </div>
                
                <div className="form-group">
                    <label htmlFor="description">Description</label>
                    <textarea
                        id="description"
                        name="description"
                        value={formData.description}
                        onChange={handleInputChange}
                        placeholder="Optional description"
                        rows="2"
                    />
                </div>
                
                <div className="form-group">
                    <label htmlFor="alert_type">Alert Type *</label>
                    <select
                        id="alert_type"
                        name="alert_type"
                        value={formData.alert_type}
                        onChange={handleInputChange}
                        className="alert-type-select"
                    >
                        {alertTypes.map(type => (
                            <option key={type.value} value={type.value}>
                                {type.label}
                            </option>
                        ))}
                    </select>
                    {currentAlertType && (
                        <div className="alert-type-description">
                            {currentAlertType.description}
                        </div>
                    )}
                </div>
                
                <div className="temperature-inputs">
                    {formData.alert_type === 'target' && (
                        <div className="form-group">
                            <label htmlFor="target_temperature">Target Temperature *</label>
                            <div className="temperature-input-group">
                                <input
                                    type="number"
                                    id="target_temperature"
                                    name="target_temperature"
                                    value={formData.target_temperature}
                                    onChange={handleInputChange}
                                    className={errors.target_temperature ? 'error' : ''}
                                    placeholder="0"
                                    step="0.1"
                                />
                                <span className="temperature-unit">°{formData.temperature_unit}</span>
                            </div>
                            {errors.target_temperature && (
                                <div className="field-error">{errors.target_temperature}</div>
                            )}
                        </div>
                    )}
                    
                    {formData.alert_type === 'range' && (
                        <>
                            <div className="form-group">
                                <label htmlFor="min_temperature">Minimum Temperature *</label>
                                <div className="temperature-input-group">
                                    <input
                                        type="number"
                                        id="min_temperature"
                                        name="min_temperature"
                                        value={formData.min_temperature}
                                        onChange={handleInputChange}
                                        className={errors.min_temperature ? 'error' : ''}
                                        placeholder="0"
                                        step="0.1"
                                    />
                                    <span className="temperature-unit">°{formData.temperature_unit}</span>
                                </div>
                                {errors.min_temperature && (
                                    <div className="field-error">{errors.min_temperature}</div>
                                )}
                            </div>
                            
                            <div className="form-group">
                                <label htmlFor="max_temperature">Maximum Temperature *</label>
                                <div className="temperature-input-group">
                                    <input
                                        type="number"
                                        id="max_temperature"
                                        name="max_temperature"
                                        value={formData.max_temperature}
                                        onChange={handleInputChange}
                                        className={errors.max_temperature ? 'error' : ''}
                                        placeholder="0"
                                        step="0.1"
                                    />
                                    <span className="temperature-unit">°{formData.temperature_unit}</span>
                                </div>
                                {errors.max_temperature && (
                                    <div className="field-error">{errors.max_temperature}</div>
                                )}
                            </div>
                        </>
                    )}
                    
                    {(formData.alert_type === 'rising' || formData.alert_type === 'falling') && (
                        <div className="form-group">
                            <label htmlFor="threshold_value">
                                Threshold ({formData.alert_type === 'rising' ? 'Rise' : 'Drop'} Amount) *
                            </label>
                            <div className="temperature-input-group">
                                <input
                                    type="number"
                                    id="threshold_value"
                                    name="threshold_value"
                                    value={formData.threshold_value}
                                    onChange={handleInputChange}
                                    className={errors.threshold_value ? 'error' : ''}
                                    placeholder="0"
                                    step="0.1"
                                    min="0.1"
                                />
                                <span className="temperature-unit">°{formData.temperature_unit}</span>
                            </div>
                            {errors.threshold_value && (
                                <div className="field-error">{errors.threshold_value}</div>
                            )}
                        </div>
                    )}
                </div>
                
                <div className="form-group">
                    <label htmlFor="temperature_unit">Temperature Unit</label>
                    <select
                        id="temperature_unit"
                        name="temperature_unit"
                        value={formData.temperature_unit}
                        onChange={handleInputChange}
                    >
                        <option value="F">Fahrenheit (°F)</option>
                        <option value="C">Celsius (°C)</option>
                    </select>
                </div>
                
                <div className="form-actions">
                    <button
                        type="button"
                        onClick={onCancel}
                        className="btn btn-secondary"
                        disabled={saving}
                    >
                        Cancel
                    </button>
                    
                    {existingAlert && (
                        <button
                            type="button"
                            onClick={handleDelete}
                            className="btn btn-danger"
                            disabled={saving}
                        >
                            {saving ? 'Deleting...' : 'Delete'}
                        </button>
                    )}
                    
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : (existingAlert ? 'Update Alert' : 'Create Alert')}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default SetAlertForm;
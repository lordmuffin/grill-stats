import React, { useState, useEffect } from 'react';
import { useApi } from '../contexts/ApiContext';

const AddDeviceForm = ({ isExpanded, onToggle, onDeviceAdded }) => {
  const [formData, setFormData] = useState({
    deviceId: '',
    nickname: ''
  });
  const [validation, setValidation] = useState({
    deviceId: { isValid: null, message: '' },
    nickname: { isValid: null, message: '' }
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState({ type: '', text: '' });
  const { deviceApi } = useApi();

  // Validation patterns
  const DEVICE_ID_PATTERN = /^TW-[A-Z0-9]{3}-[A-Z0-9]{3}$/i;
  const NICKNAME_PATTERN = /^[a-zA-Z0-9\s-_]{1,50}$/;

  // Real-time validation
  useEffect(() => {
    validateDeviceId(formData.deviceId);
  }, [formData.deviceId]);

  useEffect(() => {
    validateNickname(formData.nickname);
  }, [formData.nickname]);

  const validateDeviceId = (deviceId) => {
    if (!deviceId) {
      setValidation(prev => ({
        ...prev,
        deviceId: { isValid: null, message: '' }
      }));
      return false;
    }

    if (!DEVICE_ID_PATTERN.test(deviceId)) {
      setValidation(prev => ({
        ...prev,
        deviceId: {
          isValid: false,
          message: 'Device ID must be in format TW-XXX-XXX (e.g., TW-ABC-123)'
        }
      }));
      return false;
    }

    setValidation(prev => ({
      ...prev,
      deviceId: { isValid: true, message: 'Valid device ID format' }
    }));
    return true;
  };

  const validateNickname = (nickname) => {
    if (!nickname) {
      setValidation(prev => ({
        ...prev,
        nickname: { isValid: null, message: '' }
      }));
      return false;
    }

    if (nickname.length < 1) {
      setValidation(prev => ({
        ...prev,
        nickname: { isValid: false, message: 'Nickname is required' }
      }));
      return false;
    }

    if (nickname.length > 50) {
      setValidation(prev => ({
        ...prev,
        nickname: { isValid: false, message: 'Nickname must be 50 characters or less' }
      }));
      return false;
    }

    if (!NICKNAME_PATTERN.test(nickname)) {
      setValidation(prev => ({
        ...prev,
        nickname: {
          isValid: false,
          message: 'Nickname can only contain letters, numbers, spaces, hyphens, and underscores'
        }
      }));
      return false;
    }

    setValidation(prev => ({
      ...prev,
      nickname: { isValid: true, message: 'Valid nickname' }
    }));
    return true;
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));

    // Clear submit message when user starts typing
    if (submitMessage.text) {
      setSubmitMessage({ type: '', text: '' });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate all fields
    const isDeviceIdValid = validateDeviceId(formData.deviceId);
    const isNicknameValid = validateNickname(formData.nickname);

    if (!isDeviceIdValid || !isNicknameValid) {
      setSubmitMessage({
        type: 'error',
        text: 'Please fix the validation errors before submitting.'
      });
      return;
    }

    setIsSubmitting(true);
    setSubmitMessage({ type: '', text: '' });

    try {
      const response = await deviceApi.registerDevice(
        formData.deviceId.toUpperCase(),
        formData.nickname.trim()
      );
      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setSubmitMessage({
          type: 'success',
          text: `Device "${formData.nickname}" has been successfully registered!`
        });

        // Clear form
        setFormData({ deviceId: '', nickname: '' });
        setValidation({
          deviceId: { isValid: null, message: '' },
          nickname: { isValid: null, message: '' }
        });

        // Notify parent component
        if (onDeviceAdded) {
          onDeviceAdded(data.data);
        }

        // Auto-collapse form after success
        setTimeout(() => {
          if (onToggle) {
            onToggle();
          }
        }, 2000);

      } else {
        setSubmitMessage({
          type: 'error',
          text: data.message || 'Failed to register device. Please try again.'
        });
      }
    } catch (error) {
      console.error('Error registering device:', error);
      setSubmitMessage({
        type: 'error',
        text: 'Network error. Please check your connection and try again.'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClear = () => {
    setFormData({ deviceId: '', nickname: '' });
    setValidation({
      deviceId: { isValid: null, message: '' },
      nickname: { isValid: null, message: '' }
    });
    setSubmitMessage({ type: '', text: '' });
  };

  const isFormValid = validation.deviceId.isValid && validation.nickname.isValid;

  return (
    <div className={`add-device-form ${!isExpanded ? 'collapsed' : ''}`}>
      <div className="form-toggle" onClick={onToggle}>
        <h3>Add New Device</h3>
        <span className={`toggle-icon ${isExpanded ? 'expanded' : ''}`}>
          ▼
        </span>
      </div>

      {isExpanded && (
        <div className="form-content">
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="deviceId">
                  Device ID *
                  <span style={{ fontSize: '0.8rem', color: '#7f8c8d', marginLeft: '0.5rem' }}>
                    (Format: TW-XXX-XXX)
                  </span>
                </label>
                <input
                  type="text"
                  id="deviceId"
                  value={formData.deviceId}
                  onChange={(e) => handleInputChange('deviceId', e.target.value)}
                  placeholder="e.g., TW-ABC-123"
                  className={validation.deviceId.isValid === false ? 'error' :
                            validation.deviceId.isValid === true ? 'success' : ''}
                  disabled={isSubmitting}
                  maxLength={11}
                />
                {validation.deviceId.message && (
                  <div className={validation.deviceId.isValid ? 'form-success' : 'form-error'}>
                    {validation.deviceId.message}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="nickname">
                  Device Nickname *
                  <span style={{ fontSize: '0.8rem', color: '#7f8c8d', marginLeft: '0.5rem' }}>
                    (1-50 characters)
                  </span>
                </label>
                <input
                  type="text"
                  id="nickname"
                  value={formData.nickname}
                  onChange={(e) => handleInputChange('nickname', e.target.value)}
                  placeholder="e.g., Grill Thermometer"
                  className={validation.nickname.isValid === false ? 'error' :
                            validation.nickname.isValid === true ? 'success' : ''}
                  disabled={isSubmitting}
                  maxLength={50}
                />
                {validation.nickname.message && (
                  <div className={validation.nickname.isValid ? 'form-success' : 'form-error'}>
                    {validation.nickname.message}
                  </div>
                )}
              </div>
            </div>

            {submitMessage.text && (
              <div className={`message message-${submitMessage.type}`}>
                {submitMessage.text}
              </div>
            )}

            <div className="form-actions">
              <button
                type="button"
                onClick={handleClear}
                className="btn btn-outline"
                disabled={isSubmitting}
              >
                Clear
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={!isFormValid || isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <div className="spinner" style={{ width: '16px', height: '16px', margin: 0 }}></div>
                    Registering...
                  </>
                ) : (
                  'Register Device'
                )}
              </button>
            </div>
          </form>

          <div style={{
            marginTop: '1.5rem',
            padding: '1rem',
            backgroundColor: '#f8f9fa',
            borderRadius: '4px',
            fontSize: '0.85rem',
            color: '#6c757d'
          }}>
            <strong>Device Registration Help:</strong>
            <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem' }}>
              <li>Find your ThermoWorks device ID on the device label or in your ThermoWorks account</li>
              <li>Device ID format: TW-XXX-XXX (where X is a letter or number)</li>
              <li>Choose a memorable nickname to identify your device</li>
              <li>Make sure your device is registered with your ThermoWorks account first</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default AddDeviceForm;

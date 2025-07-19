import React, { useState, useEffect } from 'react';
import { useApi } from '../contexts/ApiContext';

const RemoveDeviceDialog = ({ device, isOpen, onClose, onDeviceRemoved }) => {
  const [isRemoving, setIsRemoving] = useState(false);
  const [removeMessage, setRemoveMessage] = useState({ type: '', text: '' });
  const [hasActiveSession, setHasActiveSession] = useState(false);
  const { deviceApi } = useApi();

  // Check if device has active sessions when dialog opens
  useEffect(() => {
    if (isOpen && device) {
      checkActiveSession();
    }
  }, [isOpen, device]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen && !isRemoving) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, isRemoving, onClose]);

  const checkActiveSession = async () => {
    try {
      // In a real implementation, you would check for active sessions
      // For now, we'll simulate this check
      // This could be an API call like: deviceApi.getActiveSession(device.device_id)

      // Mock check - you can replace this with actual session checking logic
      const mockActiveSession = Math.random() < 0.3; // 30% chance of active session
      setHasActiveSession(mockActiveSession);
    } catch (error) {
      console.error('Error checking active session:', error);
      setHasActiveSession(false);
    }
  };

  const handleRemove = async () => {
    if (!device || hasActiveSession) return;

    setIsRemoving(true);
    setRemoveMessage({ type: '', text: '' });

    try {
      const response = await deviceApi.removeDevice(device.device_id);
      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setRemoveMessage({
          type: 'success',
          text: `Device "${device.name || device.nickname}" has been successfully removed.`
        });

        // Notify parent component
        if (onDeviceRemoved) {
          onDeviceRemoved(device);
        }

        // Close dialog after short delay
        setTimeout(() => {
          onClose();
        }, 1500);

      } else {
        setRemoveMessage({
          type: 'error',
          text: data.message || 'Failed to remove device. Please try again.'
        });
      }
    } catch (error) {
      console.error('Error removing device:', error);
      setRemoveMessage({
        type: 'error',
        text: 'Network error. Please check your connection and try again.'
      });
    } finally {
      setIsRemoving(false);
    }
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget && !isRemoving) {
      onClose();
    }
  };

  if (!isOpen || !device) return null;

  const deviceName = device.name || device.nickname || device.device_id;

  return (
    <div className="dialog-overlay" onClick={handleOverlayClick}>
      <div className="dialog" role="dialog" aria-labelledby="remove-dialog-title" aria-modal="true">
        <h3 id="remove-dialog-title">Remove Device</h3>

        <div style={{ marginBottom: '1.5rem' }}>
          <p>
            Are you sure you want to remove <strong>"{deviceName}"</strong> from your account?
          </p>

          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '1rem',
            borderRadius: '4px',
            marginTop: '1rem',
            fontSize: '0.9rem'
          }}>
            <div style={{ marginBottom: '0.5rem' }}>
              <strong>Device Details:</strong>
            </div>
            <div>ID: {device.device_id}</div>
            {device.model && <div>Model: {device.model}</div>}
            {device.device_type && <div>Type: {device.device_type}</div>}
          </div>

          {hasActiveSession && (
            <div className="message message-warning" style={{ marginTop: '1rem' }}>
              <strong>Cannot remove device:</strong> This device is currently in an active monitoring session.
              Please stop the session before removing the device.
            </div>
          )}

          {!hasActiveSession && (
            <div style={{
              backgroundColor: '#fff3cd',
              color: '#856404',
              padding: '1rem',
              borderRadius: '4px',
              marginTop: '1rem',
              fontSize: '0.9rem',
              border: '1px solid #ffeaa7'
            }}>
              <strong>Warning:</strong> This action cannot be undone. All historical data and settings
              for this device will be permanently removed from your account.
            </div>
          )}
        </div>

        {removeMessage.text && (
          <div className={`message message-${removeMessage.type}`} style={{ marginBottom: '1.5rem' }}>
            {removeMessage.text}
          </div>
        )}

        <div className="dialog-actions">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-outline"
            disabled={isRemoving}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleRemove}
            className="btn btn-danger"
            disabled={isRemoving || hasActiveSession}
          >
            {isRemoving ? (
              <>
                <div className="spinner" style={{ width: '16px', height: '16px', margin: 0 }}></div>
                Removing...
              </>
            ) : (
              'Remove Device'
            )}
          </button>
        </div>

        <div style={{
          marginTop: '1rem',
          fontSize: '0.8rem',
          color: '#7f8c8d',
          textAlign: 'center'
        }}>
          Press Escape to cancel
        </div>
      </div>
    </div>
  );
};

export default RemoveDeviceDialog;

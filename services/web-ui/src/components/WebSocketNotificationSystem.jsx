import React, { useState, useEffect, useCallback, useRef } from 'react';
import io from 'socket.io-client';
import './NotificationSystem.css';

const WebSocketNotificationSystem = ({
    enableSoundAlerts = true,
    enableBrowserNotifications = true,
    fallbackPollingInterval = 10000 // 10 seconds fallback polling
}) => {
    const [notifications, setNotifications] = useState([]);
    const [isVisible, setIsVisible] = useState(false);
    const [unreadCount, setUnreadCount] = useState(0);
    const [soundEnabled, setSoundEnabled] = useState(enableSoundAlerts);
    const [browserNotificationsEnabled, setBrowserNotificationsEnabled] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');

    const socketRef = useRef(null);
    const audioRef = useRef(null);
    const fallbackIntervalRef = useRef(null);
    const notificationPermissionRef = useRef(null);

    // Initialize notification sound
    useEffect(() => {
        if (soundEnabled) {
            // Create a simple notification sound using Web Audio API
            const createNotificationSound = () => {
                try {
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const oscillator = audioContext.createOscillator();
                    const gainNode = audioContext.createGain();

                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);

                    oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
                    oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);
                    oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.2);

                    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

                    oscillator.start(audioContext.currentTime);
                    oscillator.stop(audioContext.currentTime + 0.3);

                    return audioContext;
                } catch (error) {
                    console.warn('Could not create notification sound:', error);
                    return null;
                }
            };

            audioRef.current = createNotificationSound;
        }
    }, [soundEnabled]);

    // Request browser notification permission
    useEffect(() => {
        if (enableBrowserNotifications && 'Notification' in window) {
            if (Notification.permission === 'default') {
                Notification.requestPermission().then(permission => {
                    notificationPermissionRef.current = permission;
                    setBrowserNotificationsEnabled(permission === 'granted');
                });
            } else {
                notificationPermissionRef.current = Notification.permission;
                setBrowserNotificationsEnabled(Notification.permission === 'granted');
            }
        }
    }, [enableBrowserNotifications]);

    // Fetch notifications from API (fallback)
    const fetchNotifications = useCallback(async () => {
        try {
            const response = await fetch('/api/notifications/latest', {
                credentials: 'include'
            });
            const data = await response.json();

            if (data.success) {
                const newNotifications = data.data.notifications || [];
                setNotifications(newNotifications);
                const unread = newNotifications.filter(n => !n.read).length;
                setUnreadCount(unread);
            }
        } catch (error) {
            console.error('Error fetching notifications:', error);
        }
    }, []);

    // Initialize WebSocket connection
    useEffect(() => {
        const initializeSocket = () => {
            try {
                // Create socket connection
                socketRef.current = io('/', {
                    transports: ['websocket', 'polling'],
                    upgrade: true,
                    rememberUpgrade: true
                });

                // Connection event handlers
                socketRef.current.on('connect', () => {
                    console.log('Connected to notification WebSocket');
                    setConnectionStatus('connected');
                    socketRef.current.emit('join_notifications');

                    // Clear fallback polling when WebSocket connects
                    if (fallbackIntervalRef.current) {
                        clearInterval(fallbackIntervalRef.current);
                        fallbackIntervalRef.current = null;
                    }
                });

                socketRef.current.on('disconnect', () => {
                    console.log('Disconnected from notification WebSocket');
                    setConnectionStatus('disconnected');

                    // Start fallback polling
                    if (!fallbackIntervalRef.current) {
                        fallbackIntervalRef.current = setInterval(fetchNotifications, fallbackPollingInterval);
                    }
                });

                socketRef.current.on('connect_error', (error) => {
                    console.error('WebSocket connection error:', error);
                    setConnectionStatus('error');

                    // Start fallback polling on error
                    if (!fallbackIntervalRef.current) {
                        fallbackIntervalRef.current = setInterval(fetchNotifications, fallbackPollingInterval);
                    }
                });

                // Notification event handler
                socketRef.current.on('notification', (notificationData) => {
                    console.log('Received real-time notification:', notificationData);
                    handleNewNotification(notificationData);
                });

                // Status messages
                socketRef.current.on('status', (status) => {
                    console.log('Status:', status.message);
                });

                return () => {
                    if (socketRef.current) {
                        socketRef.current.disconnect();
                    }
                };

            } catch (error) {
                console.error('Error initializing WebSocket:', error);
                setConnectionStatus('error');

                // Fall back to polling immediately
                if (!fallbackIntervalRef.current) {
                    fallbackIntervalRef.current = setInterval(fetchNotifications, fallbackPollingInterval);
                }
            }
        };

        const cleanup = initializeSocket();

        // Initial fetch
        fetchNotifications();

        return cleanup;
    }, [fetchNotifications, fallbackPollingInterval]);

    // Handle new notification
    const handleNewNotification = useCallback((notification) => {
        // Add to notifications list
        setNotifications(prev => {
            const exists = prev.some(n =>
                n.alert_id === notification.alert_id &&
                n.timestamp === notification.timestamp
            );

            if (!exists) {
                const updated = [{ ...notification, read: false }, ...prev];
                return updated.slice(0, 20); // Keep only latest 20
            }
            return prev;
        });

        // Update unread count
        setUnreadCount(prev => prev + 1);

        // Play sound alert
        if (soundEnabled && audioRef.current) {
            try {
                audioRef.current();
            } catch (error) {
                console.warn('Could not play notification sound:', error);
            }
        }

        // Show browser notification
        if (browserNotificationsEnabled && 'Notification' in window && Notification.permission === 'granted') {
            try {
                const browserNotification = new Notification(notification.alert_name || 'Temperature Alert', {
                    body: notification.message,
                    icon: '/favicon.ico',
                    tag: `alert-${notification.alert_id}-${notification.timestamp}`,
                    requireInteraction: true,
                    data: notification
                });

                // Auto-close after 10 seconds
                setTimeout(() => {
                    browserNotification.close();
                }, 10000);

            } catch (error) {
                console.warn('Could not show browser notification:', error);
            }
        }
    }, [soundEnabled, browserNotificationsEnabled]);

    // Clean up on unmount
    useEffect(() => {
        return () => {
            if (socketRef.current) {
                socketRef.current.disconnect();
            }
            if (fallbackIntervalRef.current) {
                clearInterval(fallbackIntervalRef.current);
            }
        };
    }, []);

    const toggleVisibility = () => {
        setIsVisible(!isVisible);
        if (!isVisible) {
            // Mark all notifications as read when opening
            markAllAsRead();
        }
    };

    const markAllAsRead = () => {
        setNotifications(prev => prev.map(n => ({ ...n, read: true })));
        setUnreadCount(0);
    };

    const dismissNotification = (notificationId, timestamp) => {
        setNotifications(prev => prev.filter(n =>
            !(n.alert_id === notificationId && n.timestamp === timestamp)
        ));
    };

    const clearAllNotifications = () => {
        setNotifications([]);
        setUnreadCount(0);
    };

    const sendTestNotification = () => {
        if (socketRef.current && connectionStatus === 'connected') {
            socketRef.current.emit('test_notification');
        } else {
            alert('WebSocket not connected. Cannot send test notification.');
        }
    };

    const getNotificationIcon = (alertType) => {
        switch (alertType) {
            case 'target': return '🎯';
            case 'range': return '📊';
            case 'rising': return '📈';
            case 'falling': return '📉';
            default: return '🚨';
        }
    };

    const formatTimestamp = (timestamp) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return date.toLocaleDateString();
    };

    const getConnectionStatusIcon = () => {
        switch (connectionStatus) {
            case 'connected': return '🟢';
            case 'disconnected': return '🟡';
            case 'error': return '🔴';
            default: return '⚪';
        }
    };

    const getConnectionStatusText = () => {
        switch (connectionStatus) {
            case 'connected': return 'Real-time connected';
            case 'disconnected': return 'Using fallback polling';
            case 'error': return 'Connection error - using polling';
            default: return 'Connecting...';
        }
    };

    return (
        <div className="notification-system">
            {/* Notification Bell/Button */}
            <div className="notification-trigger" onClick={toggleVisibility}>
                <div className="notification-bell">
                    🔔
                    {unreadCount > 0 && (
                        <span className="notification-badge">{unreadCount}</span>
                    )}
                    <div className="connection-status" title={getConnectionStatusText()}>
                        {getConnectionStatusIcon()}
                    </div>
                </div>
            </div>

            {/* Notification Panel */}
            {isVisible && (
                <div className="notification-panel">
                    <div className="notification-panel-header">
                        <h3>Temperature Alerts</h3>
                        <div className="notification-controls">
                            <button
                                className="control-btn"
                                onClick={() => setSoundEnabled(!soundEnabled)}
                                title={soundEnabled ? 'Disable sound alerts' : 'Enable sound alerts'}
                            >
                                {soundEnabled ? '🔊' : '🔇'}
                            </button>
                            <button
                                className="control-btn"
                                onClick={sendTestNotification}
                                title="Send test notification"
                                disabled={connectionStatus !== 'connected'}
                            >
                                🧪
                            </button>
                            <button
                                className="control-btn"
                                onClick={clearAllNotifications}
                                title="Clear all notifications"
                            >
                                🗑️
                            </button>
                            <button
                                className="control-btn close-btn"
                                onClick={toggleVisibility}
                                title="Close notifications"
                            >
                                ✕
                            </button>
                        </div>
                    </div>

                    <div className="notification-status-bar">
                        <span className="status-text">
                            {getConnectionStatusIcon()} {getConnectionStatusText()}
                        </span>
                    </div>

                    <div className="notification-list">
                        {notifications.length === 0 ? (
                            <div className="no-notifications">
                                <p>No recent notifications</p>
                                <p className="status-indicator">
                                    System is monitoring for temperature alerts
                                </p>
                            </div>
                        ) : (
                            notifications.map((notification, index) => (
                                <div
                                    key={`${notification.alert_id}-${notification.timestamp}`}
                                    className={`notification-item ${!notification.read ? 'unread' : ''}`}
                                >
                                    <div className="notification-icon">
                                        {getNotificationIcon(notification.alert_type)}
                                    </div>
                                    <div className="notification-content">
                                        <div className="notification-title">
                                            {notification.alert_name}
                                        </div>
                                        <div className="notification-message">
                                            {notification.message}
                                        </div>
                                        <div className="notification-details">
                                            <span className="device-info">
                                                {notification.device_id}/{notification.probe_id}
                                            </span>
                                            <span className="temperature-info">
                                                {notification.current_temperature}°{notification.temperature_unit}
                                            </span>
                                            <span className="timestamp">
                                                {formatTimestamp(notification.timestamp)}
                                            </span>
                                        </div>
                                    </div>
                                    <button
                                        className="dismiss-btn"
                                        onClick={() => dismissNotification(notification.alert_id, notification.timestamp)}
                                        title="Dismiss notification"
                                    >
                                        ✕
                                    </button>
                                </div>
                            ))
                        )}
                    </div>

                    {notifications.length > 0 && (
                        <div className="notification-panel-footer">
                            <small>
                                Last updated: {formatTimestamp(new Date().toISOString())}
                            </small>
                        </div>
                    )}
                </div>
            )}

            {/* Floating notification for immediate alerts */}
            {notifications.length > 0 && !isVisible && unreadCount > 0 && (
                <div className="floating-notification">
                    <div className="floating-notification-content">
                        <div className="floating-icon">
                            {getNotificationIcon(notifications[0].alert_type)}
                        </div>
                        <div className="floating-text">
                            <strong>{notifications[0].alert_name}</strong>
                            <br />
                            {notifications[0].message}
                        </div>
                        <button
                            className="floating-close"
                            onClick={() => dismissNotification(notifications[0].alert_id, notifications[0].timestamp)}
                        >
                            ✕
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default WebSocketNotificationSystem;

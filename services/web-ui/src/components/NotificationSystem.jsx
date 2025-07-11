import React, { useState, useEffect, useCallback, useRef } from 'react';
import './NotificationSystem.css';

const NotificationSystem = ({ 
    enableSoundAlerts = true, 
    enableBrowserNotifications = true,
    pollingInterval = 5000 // 5 seconds
}) => {
    const [notifications, setNotifications] = useState([]);
    const [isVisible, setIsVisible] = useState(false);
    const [unreadCount, setUnreadCount] = useState(0);
    const [soundEnabled, setSoundEnabled] = useState(enableSoundAlerts);
    const [browserNotificationsEnabled, setBrowserNotificationsEnabled] = useState(false);
    const [isPolling, setIsPolling] = useState(true);
    
    const audioRef = useRef(null);
    const pollingIntervalRef = useRef(null);
    const notificationPermissionRef = useRef(null);

    // Initialize notification sound
    useEffect(() => {
        if (soundEnabled) {
            // Create a simple notification sound using Web Audio API
            const createNotificationSound = () => {
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

    // Fetch notifications from API
    const fetchNotifications = useCallback(async () => {
        try {
            const response = await fetch('/api/notifications/latest', {
                credentials: 'include'
            });
            const data = await response.json();
            
            if (data.success) {
                const newNotifications = data.data.notifications || [];
                
                // Check for new notifications by comparing timestamps
                setNotifications(prevNotifications => {
                    const prevTimestamps = new Set(prevNotifications.map(n => n.timestamp));
                    const actuallyNewNotifications = newNotifications.filter(n => !prevTimestamps.has(n.timestamp));
                    
                    // Trigger alerts for new notifications
                    actuallyNewNotifications.forEach(notification => {
                        handleNewNotification(notification);
                    });
                    
                    return newNotifications;
                });
                
                // Update unread count
                const unread = newNotifications.filter(n => !n.read).length;
                setUnreadCount(unread);
            }
        } catch (error) {
            console.error('Error fetching notifications:', error);
        }
    }, []);

    // Handle new notification alerts
    const handleNewNotification = useCallback((notification) => {
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
                new Notification(notification.alert_name || 'Temperature Alert', {
                    body: notification.message,
                    icon: '/favicon.ico', // Assuming there's a favicon
                    tag: `alert-${notification.alert_id}`, // Prevent duplicate notifications
                    requireInteraction: true
                });
            } catch (error) {
                console.warn('Could not show browser notification:', error);
            }
        }
    }, [soundEnabled, browserNotificationsEnabled]);

    // Set up polling for new notifications
    useEffect(() => {
        if (isPolling) {
            fetchNotifications(); // Initial fetch
            
            pollingIntervalRef.current = setInterval(fetchNotifications, pollingInterval);
            
            return () => {
                if (pollingIntervalRef.current) {
                    clearInterval(pollingIntervalRef.current);
                }
            };
        }
    }, [isPolling, pollingInterval, fetchNotifications]);

    // Clean up on unmount
    useEffect(() => {
        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
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

    const dismissNotification = (notificationId) => {
        setNotifications(prev => prev.filter(n => n.alert_id !== notificationId));
    };

    const clearAllNotifications = () => {
        setNotifications([]);
        setUnreadCount(0);
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

    return (
        <div className="notification-system">
            {/* Notification Bell/Button */}
            <div className="notification-trigger" onClick={toggleVisibility}>
                <div className="notification-bell">
                    🔔
                    {unreadCount > 0 && (
                        <span className="notification-badge">{unreadCount}</span>
                    )}
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
                                onClick={() => setIsPolling(!isPolling)}
                                title={isPolling ? 'Pause notifications' : 'Resume notifications'}
                            >
                                {isPolling ? '⏸️' : '▶️'}
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

                    <div className="notification-list">
                        {notifications.length === 0 ? (
                            <div className="no-notifications">
                                <p>No recent notifications</p>
                                <span className="status-indicator">
                                    {isPolling ? (
                                        <>🟢 Monitoring active</>
                                    ) : (
                                        <>🟡 Monitoring paused</>
                                    )}
                                </span>
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
                                            <span className="timestamp">
                                                {formatTimestamp(notification.timestamp)}
                                            </span>
                                        </div>
                                    </div>
                                    <button
                                        className="dismiss-btn"
                                        onClick={() => dismissNotification(notification.alert_id)}
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
                            onClick={() => dismissNotification(notifications[0].alert_id)}
                        >
                            ✕
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default NotificationSystem;
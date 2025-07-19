import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { getDevice } from '../utils/api';
import './LiveDeviceDashboard.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

// Color palette for probe channels
const COLORS = [
  '#ff6384', // red
  '#36a2eb', // blue
  '#ffce56', // yellow
  '#4bc0c0', // teal
  '#9966ff', // purple
  '#ff9f40', // orange
  '#2ecc71', // green
  '#e74c3c', // dark red
];

/**
 * Live Device Dashboard Component for User Story 3
 * Displays real-time temperature data for selected device with channels,
 * device status, and live temperature charts
 */
const LiveDeviceDashboard = () => {
  const { deviceId } = useParams();
  const navigate = useNavigate();

  // Component state
  const [device, setDevice] = useState(null);
  const [liveData, setLiveData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  // Chart state
  const [temperatureHistory, setTemperatureHistory] = useState({});
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: []
  });

  // Refs
  const eventSourceRef = useRef(null);
  const retryTimeoutRef = useRef(null);
  const retryCount = useRef(0);
  const maxRetries = 5;

  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 0 // Disable animations for better performance
    },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          usePointStyle: true,
          boxWidth: 10,
          font: {
            size: 12
          }
        }
      },
      title: {
        display: true,
        text: `${device?.name || 'Device'} Live Temperature`,
        font: {
          size: 16,
          weight: 'bold'
        }
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const label = context.dataset.label || '';
            const value = context.parsed.y;
            return `${label}: ${value}°F`;
          },
          title: function(tooltipItems) {
            const timestamp = tooltipItems[0].label;
            const date = new Date(timestamp);
            return date.toLocaleTimeString();
          }
        }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'minute',
          displayFormats: {
            minute: 'h:mm a'
          },
          tooltipFormat: 'MMM d, h:mm:ss a'
        },
        title: {
          display: true,
          text: 'Time'
        }
      },
      y: {
        title: {
          display: true,
          text: 'Temperature (°F)'
        },
        suggestedMin: 32,
        suggestedMax: 350,
      }
    }
  };

  // Load device information
  useEffect(() => {
    const loadDevice = async () => {
      try {
        const deviceData = await getDevice(deviceId);
        setDevice(deviceData);
        setLoading(false);
      } catch (err) {
        console.error('Error loading device:', err);
        setError('Failed to load device information');
        setLoading(false);
      }
    };

    if (deviceId) {
      loadDevice();
    }
  }, [deviceId]);

  // Set up SSE connection for live data
  useEffect(() => {
    if (!deviceId) return;

    const connectToLiveStream = () => {
      try {
        setConnectionStatus('connecting');

        // Create EventSource connection
        const eventSource = new EventSource(`/api/devices/${deviceId}/stream`);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
          console.log('Live data stream connected');
          setConnectionStatus('connected');
          setError(null);
          retryCount.current = 0;
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.error) {
              console.error('Live data stream error:', data.error);
              setError(data.error);
              return;
            }

            // Update live data
            setLiveData(data);

            // Update temperature history for charts
            updateTemperatureHistory(data);

            setConnectionStatus('connected');

          } catch (err) {
            console.error('Error parsing live data:', err);
          }
        };

        eventSource.onerror = (error) => {
          console.error('Live data stream error:', error);
          setConnectionStatus('error');

          if (retryCount.current < maxRetries) {
            retryCount.current++;
            console.log(`Retrying connection... attempt ${retryCount.current}/${maxRetries}`);

            // Retry connection with exponential backoff
            retryTimeoutRef.current = setTimeout(() => {
              eventSource.close();
              connectToLiveStream();
            }, Math.min(1000 * Math.pow(2, retryCount.current), 30000));
          } else {
            setError('Unable to connect to live data stream. Please refresh the page.');
          }
        };

      } catch (err) {
        console.error('Failed to create live data stream:', err);
        setError('Failed to connect to live data stream');
      }
    };

    connectToLiveStream();

    // Cleanup
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [deviceId]);

  // Update temperature history for charts
  const updateTemperatureHistory = (data) => {
    setTemperatureHistory(prev => {
      const newHistory = { ...prev };
      const currentTime = new Date(data.timestamp);

      data.channels.forEach(channel => {
        const channelId = channel.channel_id;

        if (!newHistory[channelId]) {
          newHistory[channelId] = [];
        }

        // Add new data point
        newHistory[channelId].push({
          x: currentTime,
          y: channel.temperature,
          connected: channel.is_connected
        });

        // Keep only last 50 points (about 4 minutes at 5-second intervals)
        if (newHistory[channelId].length > 50) {
          newHistory[channelId] = newHistory[channelId].slice(-50);
        }
      });

      return newHistory;
    });
  };

  // Update chart data when temperature history changes
  useEffect(() => {
    if (!liveData || !liveData.channels) return;

    const datasets = liveData.channels.map((channel, index) => {
      const channelId = channel.channel_id;
      const history = temperatureHistory[channelId] || [];
      const color = COLORS[index % COLORS.length];

      return {
        label: channel.name,
        data: history,
        borderColor: color,
        backgroundColor: `${color}33`, // Add transparency
        borderWidth: 2,
        pointRadius: 1,
        pointHoverRadius: 5,
        tension: 0.1,
        // Show disconnected points differently
        pointBackgroundColor: history.map(point =>
          point.connected ? color : '#999999'
        )
      };
    });

    setChartData({
      datasets
    });
  }, [liveData, temperatureHistory]);

  // Handle back to device list
  const handleBackToList = () => {
    navigate('/dashboard');
  };

  // Handle connection retry
  const handleRetry = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    retryCount.current = 0;
    setError(null);
    // Trigger reconnection through useEffect
    setConnectionStatus('connecting');
    window.location.reload();
  };

  // Render loading state
  if (loading) {
    return (
      <div className="live-dashboard loading-state">
        <div className="spinner"></div>
        <p>Loading device information...</p>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="live-dashboard error-state">
        <h2>Connection Error</h2>
        <p>{error}</p>
        <div className="error-actions">
          <button onClick={handleRetry} className="retry-button">
            Retry Connection
          </button>
          <button onClick={handleBackToList} className="back-button">
            Back to Device List
          </button>
        </div>
      </div>
    );
  }

  // Render dashboard
  return (
    <div className="live-dashboard">
      <div className="dashboard-header">
        <div className="header-left">
          <button onClick={handleBackToList} className="back-button">
            ← Back to Devices
          </button>
          <h1>{device?.name || 'Unknown Device'}</h1>
        </div>
        <div className="header-right">
          <div className={`connection-status ${connectionStatus}`}>
            <span className="status-indicator"></span>
            {connectionStatus === 'connected' && 'Live'}
            {connectionStatus === 'connecting' && 'Connecting...'}
            {connectionStatus === 'error' && 'Connection Error'}
          </div>
        </div>
      </div>

      {/* Device Status Cards */}
      {liveData && liveData.status && (
        <div className="device-status-cards">
          <div className="status-card battery">
            <div className="status-icon">🔋</div>
            <div className="status-info">
              <div className="status-label">Battery Level</div>
              <div className={`status-value battery-${Math.floor(liveData.status.battery_level / 20)}`}>
                {liveData.status.battery_level}%
              </div>
            </div>
          </div>

          <div className="status-card signal">
            <div className="status-icon">📶</div>
            <div className="status-info">
              <div className="status-label">Signal Strength</div>
              <div className={`status-value signal-${Math.floor(liveData.status.signal_strength / 20)}`}>
                {liveData.status.signal_strength}%
              </div>
            </div>
          </div>

          <div className="status-card connection">
            <div className="status-icon">🔗</div>
            <div className="status-info">
              <div className="status-label">Connection</div>
              <div className={`status-value connection-${liveData.status.connection_status}`}>
                {liveData.status.connection_status}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Temperature Channels */}
      {liveData && liveData.channels && (
        <div className="temperature-channels">
          <h2>Temperature Channels</h2>
          <div className="channels-grid">
            {liveData.channels.map((channel, index) => (
              <div key={channel.channel_id} className={`channel-card ${channel.probe_type}`}>
                <div className="channel-header">
                  <h3>{channel.name}</h3>
                  <span className="probe-type">{channel.probe_type}</span>
                </div>
                <div className="temperature-display">
                  <div className="temperature-value">
                    {channel.temperature ? `${channel.temperature}°${channel.unit}` : '--'}
                  </div>
                  <div className={`connection-indicator ${channel.is_connected ? 'connected' : 'disconnected'}`}>
                    {channel.is_connected ? '●' : '○'} {channel.is_connected ? 'Connected' : 'Disconnected'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Temperature Chart */}
      {chartData.datasets.length > 0 && (
        <div className="temperature-chart">
          <h2>Temperature Trends</h2>
          <div className="chart-container">
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>
      )}

      {/* No Data State */}
      {liveData && (!liveData.channels || liveData.channels.length === 0) && (
        <div className="no-data-state">
          <h2>No Temperature Data</h2>
          <p>No temperature channels found for this device.</p>
          <p>Make sure the device is powered on and properly connected.</p>
        </div>
      )}

      {/* Data Info */}
      {liveData && (
        <div className="data-info">
          <div className="info-item">
            <strong>Last Updated:</strong> {new Date(liveData.timestamp).toLocaleString()}
          </div>
          <div className="info-item">
            <strong>Device ID:</strong> {liveData.device_id}
          </div>
          <div className="info-item">
            <strong>Active Channels:</strong> {liveData.channels.filter(c => c.is_connected).length} / {liveData.channels.length}
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveDeviceDashboard;

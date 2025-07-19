import React, { useState, useEffect, useRef } from 'react';
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
import { getCurrentTemperature, getRecentTemperatureData, getDeviceHealth } from '../utils/api';
import './RealTimeChart.css';

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

// Color palette for probe lines
const COLORS = [
  '#ff6384', // red
  '#36a2eb', // blue
  '#ffce56', // yellow
  '#4bc0c0', // teal
  '#9966ff', // purple
  '#ff9f40', // orange
  '#2ecc71', // green
  '#e74c3c', // dark red
  '#3498db', // dark blue
  '#f1c40f', // dark yellow
];

/**
 * Real-time temperature chart component
 *
 * @param {Object} props
 * @param {string} props.deviceId - Device ID to monitor
 * @param {number} props.refreshInterval - How often to refresh data in milliseconds (default: 10000)
 * @param {number} props.historyHours - How many hours of history to show (default: 1)
 * @param {number} props.height - Chart height in pixels (default: 400)
 * @param {string} props.title - Chart title (default: "Temperature Monitor")
 */
const RealTimeChart = ({
  deviceId,
  refreshInterval = 10000,
  historyHours = 1,
  height = 400,
  title = "Temperature Monitor",
}) => {
  // Chart data state
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: []
  });

  // Chart loading and error states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Device and probe states
  const [probes, setProbes] = useState([]);
  const [deviceHealth, setDeviceHealth] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Track disconnected probes
  const [disconnectedProbes, setDisconnectedProbes] = useState({});

  // Refs
  const timerRef = useRef(null);
  const chartRef = useRef(null);

  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 0 // Disable animations for better performance on frequent updates
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
        text: title,
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
            // Format timestamp in tooltip
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
        suggestedMin: 32,  // Freezing point
        suggestedMax: 350, // Hot grill temp
      }
    }
  };

  // Function to load historical data
  const loadHistoricalData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Get recent temperature data for the device
      const historyData = await getRecentTemperatureData(deviceId, historyHours);

      if (!historyData || historyData.length === 0) {
        setLoading(false);
        return; // No data yet
      }

      // Group by probe ID
      const probeMap = historyData.reduce((acc, reading) => {
        const probeId = reading.probe_id;
        if (!acc[probeId]) {
          acc[probeId] = [];
        }
        acc[probeId].push({
          x: new Date(reading.timestamp),
          y: reading.temperature
        });
        return acc;
      }, {});

      // Create a dataset for each probe
      const probeIds = Object.keys(probeMap);
      setProbes(probeIds);

      const datasets = probeIds.map((probeId, index) => {
        const color = COLORS[index % COLORS.length];
        const points = probeMap[probeId].sort((a, b) => a.x - b.x);

        return {
          label: `Probe ${probeId}`,
          data: points,
          borderColor: color,
          backgroundColor: `${color}33`, // Add transparency
          borderWidth: 2,
          pointRadius: 1,
          pointHoverRadius: 5,
          tension: 0.1
        };
      });

      // Update chart data
      setChartData({
        datasets
      });

      setLoading(false);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Error loading historical data:', err);
      setError('Failed to load historical data. Please try again.');
      setLoading(false);
    }
  };

  // Function to update with latest data
  const updateLatestData = async () => {
    if (!deviceId) return;

    try {
      // Get latest temperature readings
      const latestData = await getCurrentTemperature(deviceId, null, true);

      if (!latestData || latestData.length === 0) {
        return; // No new data
      }

      // Check for device health in parallel
      getDeviceHealth(deviceId)
        .then(health => {
          setDeviceHealth(health);
        })
        .catch(err => {
          console.error('Error fetching device health:', err);
        });

      // Process the latest readings
      const now = new Date();
      const newDisconnectedProbes = { ...disconnectedProbes };

      // Update each probe's data
      latestData.forEach(reading => {
        const probeId = reading.probe_id;
        const temperature = reading.temperature;
        const timestamp = new Date(reading.timestamp);

        // Check if this is a new probe we haven't seen before
        if (!probes.includes(probeId)) {
          setProbes(prev => [...prev, probeId]);
        }

        // Mark the probe as connected (remove from disconnected list)
        if (newDisconnectedProbes[probeId]) {
          delete newDisconnectedProbes[probeId];
        }

        // Update the chart data
        setChartData(prevData => {
          // Find existing dataset for this probe
          const existingDatasetIndex = prevData.datasets.findIndex(
            dataset => dataset.label === `Probe ${probeId}`
          );

          // Clone the datasets array
          const newDatasets = [...prevData.datasets];

          if (existingDatasetIndex >= 0) {
            // Update existing dataset
            const dataset = { ...newDatasets[existingDatasetIndex] };

            // Add new data point
            const newData = [...dataset.data, { x: timestamp, y: temperature }];

            // Keep only recent data points based on historyHours
            const cutoffTime = new Date(now - historyHours * 60 * 60 * 1000);
            const filteredData = newData.filter(point => point.x > cutoffTime);

            // Update the dataset
            dataset.data = filteredData;
            newDatasets[existingDatasetIndex] = dataset;
          } else {
            // Create new dataset for this probe
            const color = COLORS[newDatasets.length % COLORS.length];
            newDatasets.push({
              label: `Probe ${probeId}`,
              data: [{ x: timestamp, y: temperature }],
              borderColor: color,
              backgroundColor: `${color}33`,
              borderWidth: 2,
              pointRadius: 1,
              pointHoverRadius: 5,
              tension: 0.1
            });
          }

          return {
            ...prevData,
            datasets: newDatasets
          };
        });
      });

      // Check for disconnected probes
      const activeProbeIds = latestData.map(reading => reading.probe_id);
      probes.forEach(probeId => {
        if (!activeProbeIds.includes(probeId)) {
          // Probe is not in the latest data, mark as potentially disconnected
          if (!newDisconnectedProbes[probeId]) {
            newDisconnectedProbes[probeId] = {
              since: now
            };
          }
        }
      });

      setDisconnectedProbes(newDisconnectedProbes);
      setLastUpdated(now);
    } catch (err) {
      console.error('Error updating latest data:', err);
      // Don't set the error state here to avoid disrupting the display
      // Just log the error and try again next interval
    }
  };

  // Initial data loading effect
  useEffect(() => {
    if (deviceId) {
      loadHistoricalData();
    }
  }, [deviceId, historyHours]);

  // Refresh interval effect
  useEffect(() => {
    // Clear existing timer
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    if (deviceId) {
      // Initial update
      updateLatestData();

      // Set up timer for future updates
      timerRef.current = setInterval(() => {
        updateLatestData();
      }, refreshInterval);
    }

    // Cleanup
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [deviceId, refreshInterval, probes]);

  // Render states
  if (!deviceId) {
    return (
      <div className="real-time-chart empty-state">
        <p>Please select a device to monitor.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="real-time-chart error-state">
        <h3>Error</h3>
        <p>{error}</p>
        <button onClick={loadHistoricalData}>Retry</button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="real-time-chart loading-state">
        <div className="spinner"></div>
        <p>Loading temperature data...</p>
      </div>
    );
  }

  // Check if we have no data
  const hasData = chartData.datasets.some(dataset => dataset.data.length > 0);
  if (!hasData) {
    return (
      <div className="real-time-chart empty-state">
        <p>No temperature data available for this device.</p>
        <button onClick={() => updateLatestData()}>Check Again</button>
      </div>
    );
  }

  // Render chart with data
  return (
    <div className="real-time-chart">
      <div className="chart-container" style={{ height }}>
        <Line ref={chartRef} data={chartData} options={chartOptions} />
      </div>

      <div className="chart-info">
        {/* Last updated indicator */}
        <div className="last-updated">
          Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : 'Never'}
          <button className="refresh-button" onClick={updateLatestData}>
            Refresh
          </button>
        </div>

        {/* Device health indicator */}
        {deviceHealth && (
          <div className="device-health">
            <div className="health-item">
              <span className="health-label">Battery:</span>
              <span className={`health-value battery-level-${Math.floor(deviceHealth.battery_level / 20)}`}>
                {deviceHealth.battery_level}%
              </span>
            </div>
            <div className="health-item">
              <span className="health-label">Signal:</span>
              <span className={`health-value signal-strength-${Math.floor(deviceHealth.signal_strength / 20)}`}>
                {deviceHealth.signal_strength}%
              </span>
            </div>
            <div className="health-item">
              <span className="health-label">Status:</span>
              <span className={`health-value status-${deviceHealth.status}`}>
                {deviceHealth.status}
              </span>
            </div>
          </div>
        )}

        {/* Disconnected probes indicator */}
        {Object.keys(disconnectedProbes).length > 0 && (
          <div className="disconnected-probes">
            <h4>Disconnected Probes:</h4>
            <ul>
              {Object.entries(disconnectedProbes).map(([probeId, info]) => (
                <li key={probeId}>
                  Probe {probeId} - disconnected since {new Date(info.since).toLocaleTimeString()}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default RealTimeChart;

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Line } from 'react-chartjs-2';
import DatePicker from 'react-datepicker';
import { useApi } from '../contexts/ApiContext';
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
import "react-datepicker/dist/react-datepicker.css";
import './HistoricalGraph.css';

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

const HistoricalGraph = () => {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const { historicalApi } = useApi();

  // State for date range selection
  const [startDate, setStartDate] = useState(new Date(Date.now() - 24 * 60 * 60 * 1000)); // 24 hours ago
  const [endDate, setEndDate] = useState(new Date());

  // State for historical data
  const [historicalData, setHistoricalData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // State for chart configuration
  const [selectedProbes, setSelectedProbes] = useState(new Set());
  const [aggregation, setAggregation] = useState('none');
  const [interval, setInterval] = useState('1m');

  // Fetch historical data
  const fetchHistoricalData = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await historicalApi.getDeviceHistory(deviceId, {
        startTime: startDate.toISOString(),
        endTime: endDate.toISOString(),
        aggregation: aggregation,
        interval: interval,
        limit: 10000
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.status === 'success') {
        setHistoricalData(data.data);

        // Initialize selected probes to show all probes by default
        const probeIds = new Set(data.data.probes.map(probe => probe.probe_id));
        setSelectedProbes(probeIds);
      } else {
        setError(data.message || 'Failed to fetch historical data');
      }
    } catch (err) {
      setError(err.message || 'Network error while fetching historical data');
      console.error('Error fetching historical data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Initial data fetch
  useEffect(() => {
    fetchHistoricalData();
  }, [deviceId]);

  // Handle date range changes
  const handleLoadGraph = () => {
    if (startDate >= endDate) {
      setError('Start date must be before end date');
      return;
    }
    fetchHistoricalData();
  };

  // Handle probe selection toggle
  const toggleProbe = (probeId) => {
    const newSelected = new Set(selectedProbes);
    if (newSelected.has(probeId)) {
      newSelected.delete(probeId);
    } else {
      newSelected.add(probeId);
    }
    setSelectedProbes(newSelected);
  };

  // Generate chart data
  const generateChartData = () => {
    if (!historicalData || !historicalData.probes || historicalData.probes.length === 0) {
      return null;
    }

    const colors = [
      'rgb(255, 99, 132)',   // Red
      'rgb(54, 162, 235)',   // Blue
      'rgb(255, 205, 86)',   // Yellow
      'rgb(75, 192, 192)',   // Green
      'rgb(153, 102, 255)',  // Purple
      'rgb(255, 159, 64)',   // Orange
      'rgb(201, 203, 207)',  // Gray
      'rgb(255, 99, 255)',   // Pink
    ];

    const datasets = historicalData.probes
      .filter(probe => selectedProbes.has(probe.probe_id))
      .map((probe, index) => ({
        label: `Probe ${probe.probe_id}`,
        data: probe.readings.map(reading => ({
          x: new Date(reading.timestamp),
          y: reading.temperature
        })),
        borderColor: colors[index % colors.length],
        backgroundColor: colors[index % colors.length] + '20',
        fill: false,
        tension: 0.1,
        pointRadius: aggregation === 'none' ? 1 : 3,
        pointHoverRadius: 5,
      }));

    return { datasets };
  };

  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      title: {
        display: true,
        text: `Temperature History - Device ${deviceId}`,
        font: {
          size: 16
        }
      },
      legend: {
        display: true,
        position: 'top'
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            const temp = Math.round(context.parsed.y * 10) / 10;
            return `${context.dataset.label}: ${temp}°F`;
          }
        }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: {
          displayFormats: {
            minute: 'HH:mm',
            hour: 'HH:mm',
            day: 'MM/DD'
          }
        },
        title: {
          display: true,
          text: 'Time'
        },
        grid: {
          display: true,
          color: 'rgba(0, 0, 0, 0.1)'
        }
      },
      y: {
        title: {
          display: true,
          text: 'Temperature (°F)'
        },
        grid: {
          display: true,
          color: 'rgba(0, 0, 0, 0.1)'
        }
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  };

  const formatDataSummary = () => {
    if (!historicalData) return null;

    const timeDiff = endDate.getTime() - startDate.getTime();
    const hours = Math.round(timeDiff / (1000 * 60 * 60));
    const days = Math.round(hours / 24);

    return {
      timeRange: days > 1 ? `${days} days` : `${hours} hours`,
      totalReadings: historicalData.total_readings,
      probeCount: historicalData.probes.length
    };
  };

  if (loading) {
    return (
      <div className="historical-graph">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading historical data...</p>
        </div>
      </div>
    );
  }

  const dataSummary = formatDataSummary();

  return (
    <div className="historical-graph">
      <div className="graph-header">
        <div className="header-left">
          <button
            onClick={() => navigate('/devices')}
            className="btn btn-secondary"
          >
            ← Back to Devices
          </button>
          <h2>Historical Temperature Data</h2>
        </div>
      </div>

      {/* Date Range and Controls */}
      <div className="controls-panel">
        <div className="date-range-picker">
          <div className="date-input">
            <label>Start Date:</label>
            <DatePicker
              selected={startDate}
              onChange={date => setStartDate(date)}
              showTimeSelect
              timeFormat="HH:mm"
              timeIntervals={15}
              dateFormat="MMMM d, yyyy h:mm aa"
              maxDate={new Date()}
              className="date-picker-input"
            />
          </div>
          <div className="date-input">
            <label>End Date:</label>
            <DatePicker
              selected={endDate}
              onChange={date => setEndDate(date)}
              showTimeSelect
              timeFormat="HH:mm"
              timeIntervals={15}
              dateFormat="MMMM d, yyyy h:mm aa"
              minDate={startDate}
              maxDate={new Date()}
              className="date-picker-input"
            />
          </div>
        </div>

        <div className="chart-controls">
          <div className="control-group">
            <label>Aggregation:</label>
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value)}
              className="control-select"
            >
              <option value="none">Raw Data</option>
              <option value="avg">Average</option>
              <option value="min">Minimum</option>
              <option value="max">Maximum</option>
            </select>
          </div>

          {aggregation !== 'none' && (
            <div className="control-group">
              <label>Interval:</label>
              <select
                value={interval}
                onChange={(e) => setInterval(e.target.value)}
                className="control-select"
              >
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="1h">1 Hour</option>
                <option value="6h">6 Hours</option>
                <option value="1d">1 Day</option>
              </select>
            </div>
          )}
        </div>

        <button
          onClick={handleLoadGraph}
          disabled={loading}
          className="btn btn-primary"
        >
          {loading ? 'Loading...' : 'Load Graph'}
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-message">
          <p>Error: {error}</p>
        </div>
      )}

      {/* Data Summary */}
      {dataSummary && (
        <div className="data-summary">
          <p>
            Showing {dataSummary.totalReadings} readings from {dataSummary.probeCount} probe(s)
            over {dataSummary.timeRange}
          </p>
        </div>
      )}

      {/* Probe Selection */}
      {historicalData && historicalData.probes && historicalData.probes.length > 0 && (
        <div className="probe-selection">
          <h4>Select Probes to Display:</h4>
          <div className="probe-checkboxes">
            {historicalData.probes.map(probe => (
              <label key={probe.probe_id} className="probe-checkbox">
                <input
                  type="checkbox"
                  checked={selectedProbes.has(probe.probe_id)}
                  onChange={() => toggleProbe(probe.probe_id)}
                />
                <span>Probe {probe.probe_id}</span>
                <span className="reading-count">({probe.readings.length} readings)</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Historical Data Display */}
      {historicalData && (
        <div className="historical-data">
          {historicalData.probes.length === 0 ? (
            <div className="no-data-message">
              <p>No historical data found for the selected time range.</p>
              <p>Try selecting a different time period or check if your device was recording data during this time.</p>
            </div>
          ) : (
            <div className="chart-container">
              <Line
                data={generateChartData() || { datasets: [] }}
                options={chartOptions}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default HistoricalGraph;

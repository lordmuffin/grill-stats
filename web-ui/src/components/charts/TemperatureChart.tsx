import { useEffect, useRef } from 'react';
import { Box, Card, CardContent, CircularProgress, Typography, useTheme } from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  TimeScale,
  ChartData,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { useAppSelector } from '@/hooks/reduxHooks';
import { 
  selectChartTimeRange,
  selectCustomTimeRange,
  selectTemperatureUnit,
  selectChartOptions,
  selectTempRange,
} from '@/store/slices/temperatureSlice';
import useTemperatureUnit from '@/hooks/useTemperatureUnit';
import { api } from '@/store/api';
import type { Probe } from '@/types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  ChartTooltip,
  Legend,
  TimeScale,
);

interface TemperatureChartProps {
  deviceId: string;
  probeId?: string;
  probes?: Probe[];
  height?: number;
}

/**
 * Temperature history chart component
 */
const TemperatureChart = ({ deviceId, probeId, probes = [], height = 400 }: TemperatureChartProps) => {
  const theme = useTheme();
  const chartRef = useRef<ChartJS>(null);
  const { convertTemperature, getUnitSymbol } = useTemperatureUnit();
  
  const timeRange = useAppSelector(selectChartTimeRange);
  const customRange = useAppSelector(selectCustomTimeRange);
  const unit = useAppSelector(selectTemperatureUnit);
  const { showGridlines, showLegend } = useAppSelector(selectChartOptions);
  const { manual: manualTempRange, min: minTemp, max: maxTemp } = useAppSelector(selectTempRange);
  
  // Calculate time range
  const getTimeRange = () => {
    const now = new Date();
    let startTime: Date;
    let endTime = now;
    
    if (timeRange === 'custom' && customRange.start && customRange.end) {
      return {
        start: new Date(customRange.start),
        end: new Date(customRange.end),
      };
    }
    
    switch (timeRange) {
      case '15m':
        startTime = new Date(now.getTime() - 15 * 60 * 1000);
        break;
      case '1h':
        startTime = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case '6h':
        startTime = new Date(now.getTime() - 6 * 60 * 60 * 1000);
        break;
      case '24h':
        startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      default:
        startTime = new Date(now.getTime() - 60 * 60 * 1000); // Default to 1 hour
    }
    
    return { start: startTime, end: endTime };
  };
  
  const { start, end } = getTimeRange();
  
  // Fetch temperature history
  const { data: historyData, isLoading, error } = api.useGetTemperatureHistoryQuery({
    deviceId,
    probeId,
    startTime: start.toISOString(),
    endTime: end.toISOString(),
    limit: 1000,
  });
  
  // Generate colors for each probe
  const getProbeColor = (index: number) => {
    const colors = [
      '#f44336', // Red
      '#2196f3', // Blue
      '#ff9800', // Orange
      '#4caf50', // Green
      '#9c27b0', // Purple
      '#00bcd4', // Cyan
      '#ff5722', // Deep Orange
      '#8bc34a', // Light Green
    ];
    
    return colors[index % colors.length];
  };
  
  // Prepare chart data
  const prepareChartData = (): ChartData<'line'> => {
    if (!historyData || !historyData.data.readings) {
      return {
        datasets: [],
      };
    }
    
    const readings = historyData.data.readings;
    
    // If specific probe is selected or there are no probes, show single line
    if (probeId || probes.length === 0) {
      return {
        datasets: [
          {
            label: 'Temperature',
            data: readings.map(reading => ({
              x: new Date(reading.timestamp),
              y: convertTemperature(reading.temperature),
            })),
            borderColor: '#f44336',
            backgroundColor: 'rgba(244, 67, 54, 0.1)',
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.2,
            fill: true,
          },
        ],
      };
    }
    
    // Group readings by probe
    const probeReadings: Record<string, { x: Date; y: number }[]> = {};
    
    readings.forEach(reading => {
      if (!reading.probeId) return;
      
      if (!probeReadings[reading.probeId]) {
        probeReadings[reading.probeId] = [];
      }
      
      probeReadings[reading.probeId].push({
        x: new Date(reading.timestamp),
        y: convertTemperature(reading.temperature),
      });
    });
    
    // Create datasets for each probe
    return {
      datasets: probes.map((probe, index) => {
        const data = probeReadings[probe.probeId] || [];
        return {
          label: probe.name || `Probe ${probe.probeId}`,
          data,
          borderColor: getProbeColor(index),
          backgroundColor: `${getProbeColor(index)}20`,
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.2,
          fill: false,
        };
      }),
    };
  };
  
  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 500,
    },
    scales: {
      x: {
        type: 'time' as const,
        time: {
          unit: timeRange === '15m' ? 'minute' as const : 
                timeRange === '1h' ? 'minute' as const : 
                timeRange === '6h' ? 'hour' as const : 
                'hour' as const,
          displayFormats: {
            minute: 'h:mm a',
            hour: 'h a',
          },
        },
        grid: {
          display: showGridlines,
          color: theme.palette.divider,
        },
        title: {
          display: true,
          text: 'Time',
          color: theme.palette.text.secondary,
        },
      },
      y: {
        beginAtZero: false,
        grid: {
          display: showGridlines,
          color: theme.palette.divider,
        },
        title: {
          display: true,
          text: `Temperature (°${unit})`,
          color: theme.palette.text.secondary,
        },
        min: manualTempRange && minTemp !== null ? minTemp : undefined,
        max: manualTempRange && maxTemp !== null ? maxTemp : undefined,
      },
    },
    plugins: {
      legend: {
        display: showLegend,
        position: 'top' as const,
        labels: {
          color: theme.palette.text.primary,
        },
      },
      tooltip: {
        backgroundColor: theme.palette.background.paper,
        titleColor: theme.palette.text.primary,
        bodyColor: theme.palette.text.secondary,
        borderColor: theme.palette.divider,
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {
          label: (context: any) => {
            const value = context.raw.y;
            return `Temperature: ${value.toFixed(1)}${getUnitSymbol()}`;
          },
        },
      },
    },
  };
  
  // Update chart when theme changes
  useEffect(() => {
    const chart = chartRef.current;
    
    if (chart) {
      chart.update();
    }
  }, [theme.palette.mode]);
  
  if (isLoading) {
    return (
      <Card sx={{ height }}>
        <CardContent sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          height: '100%'
        }}>
          <CircularProgress />
          <Typography sx={{ ml: 2 }}>Loading temperature history...</Typography>
        </CardContent>
      </Card>
    );
  }
  
  if (error || !historyData) {
    return (
      <Card sx={{ height }}>
        <CardContent>
          <Typography variant="h6" color="error">
            Error Loading Chart Data
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Unable to fetch temperature history.
          </Typography>
        </CardContent>
      </Card>
    );
  }
  
  const chartData = prepareChartData();
  
  return (
    <Card sx={{ height }}>
      <CardContent sx={{ height: '100%', p: 2 }}>
        <Box sx={{ height: '100%', position: 'relative' }}>
          <Line
            ref={chartRef}
            data={chartData}
            options={chartOptions}
            aria-label="Temperature Chart"
          />
          
          {chartData.datasets.length === 0 && (
            <Box 
              sx={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                right: 0, 
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="body1" color="text.secondary">
                No temperature data available for the selected time range.
              </Typography>
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default TemperatureChart;
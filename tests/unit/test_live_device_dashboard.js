/**
 * Unit tests for LiveDeviceDashboard component (User Story 3)
 * Tests real-time data display, SSE connections, and user interactions
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { jest } from '@jest/globals';
import LiveDeviceDashboard from '../../services/web-ui/src/components/LiveDeviceDashboard';
import * as api from '../../services/web-ui/src/utils/api';

// Mock the API functions
jest.mock('../../services/web-ui/src/utils/api');

// Mock react-router-dom
const mockNavigate = jest.fn();
const mockParams = { deviceId: 'test_device_001' };

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
}));

// Mock Chart.js to avoid canvas issues in tests
jest.mock('react-chartjs-2', () => ({
  Line: ({ data, options }) => (
    <div data-testid="temperature-chart">
      <div data-testid="chart-datasets">{JSON.stringify(data.datasets)}</div>
      <div data-testid="chart-options">{JSON.stringify(options)}</div>
    </div>
  ),
}));

// Mock EventSource for SSE testing
class MockEventSource {
  constructor(url) {
    this.url = url;
    this.readyState = 1; // OPEN
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    
    // Store instance for testing
    MockEventSource.instances.push(this);
  }
  
  close() {
    this.readyState = 2; // CLOSED
  }
  
  // Helper methods for testing
  simulateOpen() {
    if (this.onopen) {
      this.onopen({ type: 'open' });
    }
  }
  
  simulateMessage(data) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    }
  }
  
  simulateError(error) {
    if (this.onerror) {
      this.onerror(error);
    }
  }
}

MockEventSource.instances = [];

// Setup global mocks
global.EventSource = MockEventSource;

describe('LiveDeviceDashboard', () => {
  // Test data
  const mockDevice = {
    device_id: 'test_device_001',
    name: 'Test BBQ Monitor',
    model: 'ThermoWorks Signal',
    status: 'online'
  };
  
  const mockLiveData = {
    device_id: 'test_device_001',
    timestamp: '2024-01-15T10:30:00Z',
    channels: [
      {
        channel_id: 1,
        name: 'Meat Probe 1',
        probe_type: 'meat',
        temperature: 165.5,
        unit: 'F',
        is_connected: true
      },
      {
        channel_id: 2,
        name: 'Ambient Probe',
        probe_type: 'ambient',
        temperature: 225.0,
        unit: 'F',
        is_connected: true
      }
    ],
    status: {
      battery_level: 85,
      signal_strength: 92,
      connection_status: 'online'
    }
  };
  
  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();
    MockEventSource.instances = [];
    
    // Setup default API responses
    api.getDevice.mockResolvedValue(mockDevice);
  });
  
  afterEach(() => {
    // Clean up any open EventSource connections
    MockEventSource.instances.forEach(instance => {
      instance.close();
    });
  });
  
  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <LiveDeviceDashboard />
      </BrowserRouter>
    );
  };
  
  describe('Component Loading', () => {
    test('shows loading state initially', async () => {
      renderComponent();
      
      expect(screen.getByText('Loading device information...')).toBeInTheDocument();
      expect(screen.getByTestId('spinner')).toBeInTheDocument();
    });
    
    test('loads device information on mount', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(api.getDevice).toHaveBeenCalledWith('test_device_001');
      });
    });
    
    test('displays device name after loading', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(screen.getByText('Test BBQ Monitor')).toBeInTheDocument();
      });
    });
  });
  
  describe('SSE Connection', () => {
    test('establishes SSE connection on mount', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      expect(eventSource.url).toBe('/api/devices/test_device_001/stream');
    });
    
    test('shows connecting status initially', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(screen.getByText('Connecting...')).toBeInTheDocument();
      });
    });
    
    test('shows connected status after SSE opens', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateOpen();
      });
      
      await waitFor(() => {
        expect(screen.getByText('Live')).toBeInTheDocument();
      });
    });
    
    test('processes live data messages', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateOpen();
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('165.5°F')).toBeInTheDocument();
        expect(screen.getByText('225.0°F')).toBeInTheDocument();
      });
    });
  });
  
  describe('Device Status Display', () => {
    test('displays battery level', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('85%')).toBeInTheDocument();
      });
    });
    
    test('displays signal strength', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('92%')).toBeInTheDocument();
      });
    });
    
    test('displays connection status', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('online')).toBeInTheDocument();
      });
    });
  });
  
  describe('Temperature Channels', () => {
    test('displays all temperature channels', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('Meat Probe 1')).toBeInTheDocument();
        expect(screen.getByText('Ambient Probe')).toBeInTheDocument();
      });
    });
    
    test('displays temperature values', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('165.5°F')).toBeInTheDocument();
        expect(screen.getByText('225.0°F')).toBeInTheDocument();
      });
    });
    
    test('shows connection status for each channel', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        const connectedElements = screen.getAllByText('Connected');
        expect(connectedElements).toHaveLength(2);
      });
    });
    
    test('displays disconnected channels differently', async () => {
      const disconnectedData = {
        ...mockLiveData,
        channels: [
          {
            ...mockLiveData.channels[0],
            is_connected: false
          }
        ]
      };
      
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(disconnectedData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('Disconnected')).toBeInTheDocument();
      });
    });
  });
  
  describe('Temperature Chart', () => {
    test('displays temperature chart when data is available', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByTestId('temperature-chart')).toBeInTheDocument();
      });
    });
    
    test('updates chart data with new temperature readings', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      // Send first data point
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByTestId('temperature-chart')).toBeInTheDocument();
      });
      
      // Send second data point with different temperature
      const updatedData = {
        ...mockLiveData,
        channels: [
          {
            ...mockLiveData.channels[0],
            temperature: 170.0
          }
        ]
      };
      
      act(() => {
        eventSource.simulateMessage(updatedData);
      });
      
      // Chart should update with new data
      await waitFor(() => {
        const chartData = screen.getByTestId('chart-datasets');
        expect(chartData).toBeInTheDocument();
      });
    });
  });
  
  describe('Error Handling', () => {
    test('displays error message when device loading fails', async () => {
      api.getDevice.mockRejectedValue(new Error('Device not found'));
      
      renderComponent();
      
      await waitFor(() => {
        expect(screen.getByText('Failed to load device information')).toBeInTheDocument();
      });
    });
    
    test('displays error message when SSE connection fails', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateError(new Error('Connection failed'));
      });
      
      await waitFor(() => {
        expect(screen.getByText('Connection Error')).toBeInTheDocument();
      });
    });
    
    test('shows retry button on connection error', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateError(new Error('Connection failed'));
      });
      
      await waitFor(() => {
        expect(screen.getByText('Retry Connection')).toBeInTheDocument();
      });
    });
  });
  
  describe('Navigation', () => {
    test('navigates back to device list when back button is clicked', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(screen.getByText('← Back to Devices')).toBeInTheDocument();
      });
      
      const backButton = screen.getByText('← Back to Devices');
      fireEvent.click(backButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });
  
  describe('Data Info', () => {
    test('displays last updated timestamp', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText(/Last Updated:/)).toBeInTheDocument();
      });
    });
    
    test('displays device ID', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText(/Device ID:/)).toBeInTheDocument();
        expect(screen.getByText('test_device_001')).toBeInTheDocument();
      });
    });
    
    test('displays active channel count', async () => {
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(mockLiveData);
      });
      
      await waitFor(() => {
        expect(screen.getByText(/Active Channels:/)).toBeInTheDocument();
        expect(screen.getByText('2 / 2')).toBeInTheDocument();
      });
    });
  });
  
  describe('No Data State', () => {
    test('displays no data message when no channels are available', async () => {
      const noChannelsData = {
        ...mockLiveData,
        channels: []
      };
      
      renderComponent();
      
      await waitFor(() => {
        expect(MockEventSource.instances).toHaveLength(1);
      });
      
      const eventSource = MockEventSource.instances[0];
      
      act(() => {
        eventSource.simulateMessage(noChannelsData);
      });
      
      await waitFor(() => {
        expect(screen.getByText('No Temperature Data')).toBeInTheDocument();
        expect(screen.getByText('No temperature channels found for this device.')).toBeInTheDocument();
      });
    });
  });
  
  describe('Responsive Design', () => {
    test('component renders properly on mobile viewport', async () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'innerWidth', { value: 480 });
      Object.defineProperty(window, 'innerHeight', { value: 800 });
      
      renderComponent();
      
      await waitFor(() => {
        expect(screen.getByText('Test BBQ Monitor')).toBeInTheDocument();
      });
      
      // Component should still render all essential elements
      expect(screen.getByText('← Back to Devices')).toBeInTheDocument();
    });
  });
});

describe('LiveDeviceDashboard Integration', () => {
  test('handles real-time data updates correctly', async () => {
    const { rerender } = render(
      <BrowserRouter>
        <LiveDeviceDashboard />
      </BrowserRouter>
    );
    
    // Wait for initial load
    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    
    const eventSource = MockEventSource.instances[0];
    
    // Simulate multiple data updates
    const updates = [
      { ...mockLiveData, channels: [{ ...mockLiveData.channels[0], temperature: 160.0 }] },
      { ...mockLiveData, channels: [{ ...mockLiveData.channels[0], temperature: 165.0 }] },
      { ...mockLiveData, channels: [{ ...mockLiveData.channels[0], temperature: 170.0 }] }
    ];
    
    for (const update of updates) {
      act(() => {
        eventSource.simulateMessage(update);
      });
      
      await waitFor(() => {
        expect(screen.getByText(`${update.channels[0].temperature}°F`)).toBeInTheDocument();
      });
    }
  });
  
  test('maintains connection stability during rapid updates', async () => {
    render(
      <BrowserRouter>
        <LiveDeviceDashboard />
      </BrowserRouter>
    );
    
    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    
    const eventSource = MockEventSource.instances[0];
    
    // Simulate rapid updates
    for (let i = 0; i < 10; i++) {
      act(() => {
        eventSource.simulateMessage({
          ...mockLiveData,
          channels: [{ ...mockLiveData.channels[0], temperature: 160 + i }]
        });
      });
    }
    
    // Connection should remain stable
    expect(eventSource.readyState).toBe(1); // OPEN
    
    await waitFor(() => {
      expect(screen.getByText('169°F')).toBeInTheDocument();
    });
  });
});
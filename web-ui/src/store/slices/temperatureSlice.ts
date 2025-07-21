import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { TemperatureReading, ChartSeries } from '@/types';

interface TemperatureState {
  realtimeEnabled: boolean;
  chartTimeRange: '15m' | '1h' | '6h' | '24h' | 'custom';
  customStartTime: string | null;
  customEndTime: string | null;
  temperatureUnit: 'F' | 'C';
  autoRefresh: boolean;
  refreshInterval: number; // in milliseconds
  chartData: Record<string, ChartSeries>;
  latestReadings: Record<string, TemperatureReading>;
  showGridlines: boolean;
  showLegend: boolean;
  manualTempRange: boolean;
  minTemp: number | null;
  maxTemp: number | null;
}

const initialState: TemperatureState = {
  realtimeEnabled: true,
  chartTimeRange: '1h',
  customStartTime: null,
  customEndTime: null,
  temperatureUnit: 'F',
  autoRefresh: true,
  refreshInterval: 5000, // 5 seconds default
  chartData: {},
  latestReadings: {},
  showGridlines: true,
  showLegend: true,
  manualTempRange: false,
  minTemp: null,
  maxTemp: null,
};

const temperatureSlice = createSlice({
  name: 'temperature',
  initialState,
  reducers: {
    setRealtimeEnabled: (state, action: PayloadAction<boolean>) => {
      state.realtimeEnabled = action.payload;
    },
    setChartTimeRange: (state, action: PayloadAction<'15m' | '1h' | '6h' | '24h' | 'custom'>) => {
      state.chartTimeRange = action.payload;
    },
    setCustomTimeRange: (state, action: PayloadAction<{ start: string | null; end: string | null }>) => {
      state.customStartTime = action.payload.start;
      state.customEndTime = action.payload.end;
      if (action.payload.start && action.payload.end) {
        state.chartTimeRange = 'custom';
      }
    },
    setTemperatureUnit: (state, action: PayloadAction<'F' | 'C'>) => {
      state.temperatureUnit = action.payload;
    },
    setAutoRefresh: (state, action: PayloadAction<boolean>) => {
      state.autoRefresh = action.payload;
    },
    setRefreshInterval: (state, action: PayloadAction<number>) => {
      state.refreshInterval = action.payload;
    },
    addChartSeries: (state, action: PayloadAction<{ id: string; series: ChartSeries }>) => {
      state.chartData[action.payload.id] = action.payload.series;
    },
    updateChartSeries: (state, action: PayloadAction<{ id: string; series: Partial<ChartSeries> }>) => {
      if (state.chartData[action.payload.id]) {
        state.chartData[action.payload.id] = {
          ...state.chartData[action.payload.id],
          ...action.payload.series,
        };
      }
    },
    removeChartSeries: (state, action: PayloadAction<string>) => {
      delete state.chartData[action.payload];
    },
    clearChartData: (state) => {
      state.chartData = {};
    },
    addTemperatureReading: (state, action: PayloadAction<{ deviceId: string; probeId?: string; reading: TemperatureReading }>) => {
      const key = `${action.payload.deviceId}${action.payload.probeId ? `-${action.payload.probeId}` : ''}`;
      state.latestReadings[key] = action.payload.reading;
    },
    clearTemperatureReadings: (state) => {
      state.latestReadings = {};
    },
    setChartOptions: (state, action: PayloadAction<{ showGridlines?: boolean; showLegend?: boolean }>) => {
      if (action.payload.showGridlines !== undefined) {
        state.showGridlines = action.payload.showGridlines;
      }
      if (action.payload.showLegend !== undefined) {
        state.showLegend = action.payload.showLegend;
      }
    },
    setManualTempRange: (state, action: PayloadAction<{ enabled: boolean; min?: number | null; max?: number | null }>) => {
      state.manualTempRange = action.payload.enabled;
      if (action.payload.min !== undefined) {
        state.minTemp = action.payload.min;
      }
      if (action.payload.max !== undefined) {
        state.maxTemp = action.payload.max;
      }
    },
  },
});

// Export actions
export const {
  setRealtimeEnabled,
  setChartTimeRange,
  setCustomTimeRange,
  setTemperatureUnit,
  setAutoRefresh,
  setRefreshInterval,
  addChartSeries,
  updateChartSeries,
  removeChartSeries,
  clearChartData,
  addTemperatureReading,
  clearTemperatureReadings,
  setChartOptions,
  setManualTempRange,
} = temperatureSlice.actions;

// Export selectors
export const selectRealtimeEnabled = (state: RootState) => state.temperature.realtimeEnabled;
export const selectChartTimeRange = (state: RootState) => state.temperature.chartTimeRange;
export const selectCustomTimeRange = (state: RootState) => ({
  start: state.temperature.customStartTime,
  end: state.temperature.customEndTime,
});
export const selectTemperatureUnit = (state: RootState) => state.temperature.temperatureUnit;
export const selectAutoRefresh = (state: RootState) => state.temperature.autoRefresh;
export const selectRefreshInterval = (state: RootState) => state.temperature.refreshInterval;
export const selectChartData = (state: RootState) => state.temperature.chartData;
export const selectLatestReadings = (state: RootState) => state.temperature.latestReadings;
export const selectChartOptions = (state: RootState) => ({
  showGridlines: state.temperature.showGridlines,
  showLegend: state.temperature.showLegend,
});
export const selectTempRange = (state: RootState) => ({
  manual: state.temperature.manualTempRange,
  min: state.temperature.minTemp,
  max: state.temperature.maxTemp,
});

export default temperatureSlice.reducer;
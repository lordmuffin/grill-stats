// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
  errors: string[];
  timestamp: string;
}

// User types
export interface User {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  createdAt: string;
  lastLogin?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RegisterData {
  email: string;
  password: string;
  confirmPassword: string;
  firstName?: string;
  lastName?: string;
}

// Device types
export interface Device {
  id: string;
  deviceId: string;
  nickname?: string;
  userId: string;
  status: 'online' | 'offline' | 'unknown';
  lastConnection?: string;
  batteryLevel?: number;
  signalStrength?: number;
  probes?: Probe[];
  createdAt: string;
  updatedAt: string;
}

export interface Probe {
  id: string;
  deviceId: string;
  probeId: string;
  name?: string;
  type: string;
  currentTemperature?: number;
  lastReading?: string;
  status: 'connected' | 'disconnected' | 'unknown';
}

// Temperature types
export interface TemperatureReading {
  deviceId: string;
  probeId?: string;
  temperature: number;
  timestamp: string;
  batteryLevel?: number;
  signalStrength?: number;
}

export interface TemperatureHistory {
  readings: TemperatureReading[];
  count: number;
  deviceId: string;
  probeId?: string;
  startTime?: string;
  endTime?: string;
}

export interface TemperatureStats {
  deviceId: string;
  probeId?: string;
  minTemperature: number;
  maxTemperature: number;
  avgTemperature: number;
  currentTemperature?: number;
  startTime: string;
  endTime: string;
  readingCount: number;
}

export interface TemperatureAlert {
  id: string;
  deviceId: string;
  probeId?: string;
  type: 'high' | 'low' | 'disconnected' | 'reconnected' | 'battery';
  threshold?: number;
  actualValue: number;
  timestamp: string;
  acknowledged: boolean;
  message: string;
}

// Chart data types
export interface ChartDataPoint {
  x: number | string;
  y: number;
}

export interface ChartSeries {
  label: string;
  data: ChartDataPoint[];
  borderColor?: string;
  backgroundColor?: string;
}

// Theme
export type ThemeMode = 'light' | 'dark';

// Environment variables
export interface AppConfig {
  apiBaseUrl: string;
  authEnabled: boolean;
  websocketUrl: string;
  temperatureRefreshRate: number;
}
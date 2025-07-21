import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { 
  ApiResponse, 
  Device, 
  TemperatureReading, 
  TemperatureHistory,
  TemperatureStats,
  TemperatureAlert,
  User,
} from '@/types';

// Read the API base URL from environment variable
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

// Define our API service
export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ 
    baseUrl: apiBaseUrl,
    credentials: 'include', // Send cookies with every request
    prepareHeaders: (headers) => {
      // You can add auth headers here if needed
      return headers;
    },
  }),
  tagTypes: ['Device', 'Temperature', 'User', 'Alert'],
  endpoints: (builder) => ({
    // Auth endpoints
    login: builder.mutation<ApiResponse<User>, { email: string; password: string; rememberMe?: boolean }>({
      query: (credentials) => ({
        url: '/auth/login',
        method: 'POST',
        body: credentials,
      }),
      invalidatesTags: ['User'],
    }),
    
    logout: builder.mutation<ApiResponse<null>, void>({
      query: () => ({
        url: '/auth/logout',
        method: 'POST',
      }),
      invalidatesTags: ['User', 'Device', 'Temperature', 'Alert'],
    }),
    
    register: builder.mutation<ApiResponse<User>, { email: string; password: string; confirmPassword: string; firstName?: string; lastName?: string }>({
      query: (userData) => ({
        url: '/auth/register',
        method: 'POST',
        body: userData,
      }),
    }),
    
    getCurrentUser: builder.query<ApiResponse<User>, void>({
      query: () => '/auth/user',
      providesTags: ['User'],
    }),
    
    // Device endpoints
    getDevices: builder.query<ApiResponse<{ devices: Device[]; count: number }>, { status?: string; includeInactive?: boolean }>({
      query: (params) => ({
        url: '/devices',
        method: 'GET',
        params,
      }),
      providesTags: (result) => 
        result?.data.devices
          ? [
              ...result.data.devices.map(({ id }) => ({ type: 'Device' as const, id })),
              { type: 'Device', id: 'LIST' },
            ]
          : [{ type: 'Device', id: 'LIST' }],
    }),
    
    getDeviceById: builder.query<ApiResponse<Device>, string>({
      query: (deviceId) => `/devices/${deviceId}`,
      providesTags: (result, _error, deviceId) => [{ type: 'Device', id: deviceId }],
    }),
    
    registerDevice: builder.mutation<ApiResponse<Device>, { deviceId: string; nickname?: string }>({
      query: (deviceData) => ({
        url: '/devices/register',
        method: 'POST',
        body: deviceData,
      }),
      invalidatesTags: [{ type: 'Device', id: 'LIST' }],
    }),
    
    updateDeviceNickname: builder.mutation<ApiResponse<Device>, { deviceId: string; nickname: string }>({
      query: ({ deviceId, nickname }) => ({
        url: `/devices/${deviceId}/nickname`,
        method: 'PUT',
        body: { nickname },
      }),
      invalidatesTags: (_result, _error, { deviceId }) => [
        { type: 'Device', id: deviceId },
        { type: 'Device', id: 'LIST' },
      ],
    }),
    
    removeDevice: builder.mutation<ApiResponse<null>, string>({
      query: (deviceId) => ({
        url: `/devices/${deviceId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, deviceId) => [
        { type: 'Device', id: deviceId },
        { type: 'Device', id: 'LIST' },
      ],
    }),
    
    // Temperature endpoints
    getCurrentTemperature: builder.query<ApiResponse<TemperatureReading>, { deviceId: string; probeId?: string }>({
      query: ({ deviceId, probeId }) => ({
        url: `/temperature/current/${deviceId}`,
        method: 'GET',
        params: probeId ? { probe_id: probeId } : undefined,
      }),
      providesTags: (_result, _error, { deviceId, probeId }) => [
        { type: 'Temperature', id: `${deviceId}${probeId ? `-${probeId}` : ''}-current` },
      ],
    }),
    
    getTemperatureHistory: builder.query<
      ApiResponse<TemperatureHistory>,
      { 
        deviceId: string; 
        probeId?: string; 
        startTime?: string; 
        endTime?: string;
        aggregation?: string;
        interval?: string;
        limit?: number;
        offset?: number;
      }
    >({
      query: ({ 
        deviceId, 
        probeId, 
        startTime, 
        endTime,
        aggregation,
        interval,
        limit,
        offset,
      }) => ({
        url: `/temperature/history/${deviceId}`,
        method: 'GET',
        params: {
          ...(probeId && { probe_id: probeId }),
          ...(startTime && { start_time: startTime }),
          ...(endTime && { end_time: endTime }),
          ...(aggregation && { aggregation }),
          ...(interval && { interval }),
          ...(limit && { limit }),
          ...(offset && { offset }),
        },
      }),
      providesTags: (_result, _error, { deviceId, probeId }) => [
        { type: 'Temperature', id: `${deviceId}${probeId ? `-${probeId}` : ''}-history` },
      ],
    }),
    
    getTemperatureStats: builder.query<
      ApiResponse<TemperatureStats>,
      { 
        deviceId: string; 
        probeId?: string; 
        startTime?: string; 
        endTime?: string;
      }
    >({
      query: ({ deviceId, probeId, startTime, endTime }) => ({
        url: `/temperature/stats/${deviceId}`,
        method: 'GET',
        params: {
          ...(probeId && { probe_id: probeId }),
          ...(startTime && { start_time: startTime }),
          ...(endTime && { end_time: endTime }),
        },
      }),
      providesTags: (_result, _error, { deviceId, probeId }) => [
        { type: 'Temperature', id: `${deviceId}${probeId ? `-${probeId}` : ''}-stats` },
      ],
    }),
    
    // Alert endpoints
    getTemperatureAlerts: builder.query<
      ApiResponse<{ alerts: TemperatureAlert[]; count: number }>,
      { 
        deviceId: string; 
        probeId?: string; 
        startTime?: string; 
        endTime?: string;
        thresholdHigh?: number;
        thresholdLow?: number;
      }
    >({
      query: ({ 
        deviceId, 
        probeId, 
        startTime, 
        endTime,
        thresholdHigh,
        thresholdLow,
      }) => ({
        url: `/temperature/alerts/${deviceId}`,
        method: 'GET',
        params: {
          ...(probeId && { probe_id: probeId }),
          ...(startTime && { start_time: startTime }),
          ...(endTime && { end_time: endTime }),
          ...(thresholdHigh && { threshold_high: thresholdHigh }),
          ...(thresholdLow && { threshold_low: thresholdLow }),
        },
      }),
      providesTags: (result) => 
        result?.data.alerts
          ? [
              ...result.data.alerts.map(({ id }) => ({ type: 'Alert' as const, id })),
              { type: 'Alert', id: 'LIST' },
            ]
          : [{ type: 'Alert', id: 'LIST' }],
    }),
    
    acknowledgeAlert: builder.mutation<ApiResponse<TemperatureAlert>, string>({
      query: (alertId) => ({
        url: `/alerts/${alertId}/acknowledge`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, alertId) => [
        { type: 'Alert', id: alertId },
        { type: 'Alert', id: 'LIST' },
      ],
    }),
  }),
});
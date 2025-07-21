import type { AppConfig } from '@/types';

/**
 * Application configuration
 * Loads values from environment variables with fallbacks
 */
const config: AppConfig = {
  // API base URL
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api',
  
  // Authentication enabled
  authEnabled: import.meta.env.VITE_AUTH_ENABLED !== 'false',
  
  // WebSocket URL for real-time updates
  websocketUrl: import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:5000',
  
  // Temperature refresh rate in milliseconds
  temperatureRefreshRate: parseInt(import.meta.env.VITE_TEMPERATURE_REFRESH_RATE || '5000', 10),
};

export default config;
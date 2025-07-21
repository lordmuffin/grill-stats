import { useEffect, useState } from 'react';
import { useAppDispatch, useAppSelector } from './reduxHooks';
import { addTemperatureReading } from '@/store/slices/temperatureSlice';
import { selectRealtimeEnabled } from '@/store/slices/temperatureSlice';
import { addAlert, generateAlertId } from '@/store/slices/uiSlice';
import type { TemperatureReading } from '@/types';

/**
 * Hook to establish WebSocket connection for real-time temperature updates
 * 
 * @param deviceId The ID of the device to monitor
 * @param probeId Optional probe ID to filter data
 * @returns Object with connection status and error information
 */
export const useTemperatureSocket = (deviceId: string, probeId?: string) => {
  const dispatch = useAppDispatch();
  const realtimeEnabled = useAppSelector(selectRealtimeEnabled);
  
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    
    // Only connect if real-time updates are enabled
    if (!realtimeEnabled || !deviceId) {
      return;
    }
    
    const connect = () => {
      const websocketUrl = import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:5000';
      const wsUrl = `${websocketUrl}/temperature/ws/${deviceId}${probeId ? `?probe_id=${probeId}` : ''}`;
      
      try {
        socket = new WebSocket(wsUrl);
        
        socket.onopen = () => {
          setConnected(true);
          setError(null);
          console.log(`WebSocket connected for device ${deviceId}`);
        };
        
        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as TemperatureReading;
            dispatch(addTemperatureReading({
              deviceId,
              probeId,
              reading: data,
            }));
          } catch (err) {
            console.error('Error parsing WebSocket message:', err);
          }
        };
        
        socket.onerror = (event) => {
          console.error('WebSocket error:', event);
          setError('WebSocket connection error');
          setConnected(false);
        };
        
        socket.onclose = (event) => {
          setConnected(false);
          
          if (event.code !== 1000) {
            // Abnormal closure, attempt to reconnect
            setError(`Connection closed (code ${event.code}). Reconnecting...`);
            
            if (reconnectTimer) {
              window.clearTimeout(reconnectTimer);
            }
            
            reconnectTimer = window.setTimeout(() => {
              connect();
            }, 5000);
          } else {
            setError(null);
          }
          
          console.log(`WebSocket closed for device ${deviceId}`);
        };
      } catch (err) {
        setError(`Failed to establish WebSocket connection: ${(err as Error).message}`);
        setConnected(false);
        
        // Try to reconnect after a delay
        if (reconnectTimer) {
          window.clearTimeout(reconnectTimer);
        }
        
        reconnectTimer = window.setTimeout(() => {
          connect();
        }, 5000);
      }
    };
    
    connect();
    
    // Cleanup when the component unmounts or dependencies change
    return () => {
      if (socket) {
        socket.close(1000, 'Component unmounted');
      }
      
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
    };
  }, [deviceId, probeId, realtimeEnabled, dispatch]);
  
  useEffect(() => {
    if (error) {
      dispatch(addAlert({
        id: generateAlertId(),
        type: 'warning',
        message: `Real-time connection issue: ${error}`,
        autoHide: true,
        duration: 5000,
      }));
    }
  }, [error, dispatch]);
  
  return {
    connected,
    error,
  };
};

export default useTemperatureSocket;
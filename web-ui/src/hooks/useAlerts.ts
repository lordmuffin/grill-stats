import { useCallback } from 'react';
import { useAppDispatch } from './reduxHooks';
import { addAlert, removeAlert, generateAlertId } from '@/store/slices/uiSlice';
import type { AlertNotification } from '@/types';

/**
 * Hook to manage UI alerts and notifications
 * 
 * @returns Functions for showing and dismissing alerts
 */
export const useAlerts = () => {
  const dispatch = useAppDispatch();
  
  /**
   * Show a success alert
   * 
   * @param message The message to display
   * @param autoHide Whether to automatically hide the alert (default: true)
   * @param duration Duration in milliseconds before auto-hiding (default: 5000)
   * @returns Alert ID
   */
  const showSuccess = useCallback((
    message: string,
    autoHide = true,
    duration = 5000,
  ): string => {
    const id = generateAlertId();
    dispatch(addAlert({
      id,
      type: 'success',
      message,
      autoHide,
      duration,
    }));
    return id;
  }, [dispatch]);
  
  /**
   * Show an error alert
   * 
   * @param message The message to display
   * @param autoHide Whether to automatically hide the alert (default: false)
   * @param duration Duration in milliseconds before auto-hiding (default: 0)
   * @returns Alert ID
   */
  const showError = useCallback((
    message: string,
    autoHide = false,
    duration = 0,
  ): string => {
    const id = generateAlertId();
    dispatch(addAlert({
      id,
      type: 'error',
      message,
      autoHide,
      duration,
    }));
    return id;
  }, [dispatch]);
  
  /**
   * Show a warning alert
   * 
   * @param message The message to display
   * @param autoHide Whether to automatically hide the alert (default: true)
   * @param duration Duration in milliseconds before auto-hiding (default: 7000)
   * @returns Alert ID
   */
  const showWarning = useCallback((
    message: string,
    autoHide = true,
    duration = 7000,
  ): string => {
    const id = generateAlertId();
    dispatch(addAlert({
      id,
      type: 'warning',
      message,
      autoHide,
      duration,
    }));
    return id;
  }, [dispatch]);
  
  /**
   * Show an info alert
   * 
   * @param message The message to display
   * @param autoHide Whether to automatically hide the alert (default: true)
   * @param duration Duration in milliseconds before auto-hiding (default: 5000)
   * @returns Alert ID
   */
  const showInfo = useCallback((
    message: string,
    autoHide = true,
    duration = 5000,
  ): string => {
    const id = generateAlertId();
    dispatch(addAlert({
      id,
      type: 'info',
      message,
      autoHide,
      duration,
    }));
    return id;
  }, [dispatch]);
  
  /**
   * Show a custom alert
   * 
   * @param alert The alert notification object
   * @returns Alert ID
   */
  const showAlert = useCallback((alert: Omit<AlertNotification, 'id'>): string => {
    const id = generateAlertId();
    dispatch(addAlert({
      id,
      ...alert,
    }));
    return id;
  }, [dispatch]);
  
  /**
   * Dismiss an alert
   * 
   * @param id The ID of the alert to dismiss
   */
  const dismissAlert = useCallback((id: string): void => {
    dispatch(removeAlert(id));
  }, [dispatch]);
  
  return {
    showSuccess,
    showError,
    showWarning,
    showInfo,
    showAlert,
    dismissAlert,
  };
};

export default useAlerts;
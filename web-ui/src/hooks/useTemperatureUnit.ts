import { useCallback } from 'react';
import { useAppSelector } from './reduxHooks';
import { selectTemperatureUnit } from '@/store/slices/temperatureSlice';

/**
 * Hook to help with temperature unit conversion and formatting
 * 
 * @returns Functions for converting and formatting temperature values
 */
export const useTemperatureUnit = () => {
  const unit = useAppSelector(selectTemperatureUnit);
  
  /**
   * Converts Fahrenheit to Celsius
   * 
   * @param fahrenheit Temperature in Fahrenheit
   * @returns Temperature in Celsius
   */
  const toCelsius = useCallback((fahrenheit: number): number => {
    return (fahrenheit - 32) * 5 / 9;
  }, []);
  
  /**
   * Converts Celsius to Fahrenheit
   * 
   * @param celsius Temperature in Celsius
   * @returns Temperature in Fahrenheit
   */
  const toFahrenheit = useCallback((celsius: number): number => {
    return (celsius * 9 / 5) + 32;
  }, []);
  
  /**
   * Converts temperature based on selected unit
   * 
   * @param value Temperature value (always stored as Fahrenheit in the API)
   * @returns Converted temperature value
   */
  const convertTemperature = useCallback((value: number): number => {
    if (unit === 'C') {
      return toCelsius(value);
    }
    return value;
  }, [unit, toCelsius]);
  
  /**
   * Formats temperature for display
   * 
   * @param value Temperature value (always stored as Fahrenheit in the API)
   * @param precision Number of decimal places
   * @returns Formatted temperature string with unit
   */
  const formatTemperature = useCallback((value: number, precision = 1): string => {
    const converted = convertTemperature(value);
    return `${converted.toFixed(precision)}°${unit}`;
  }, [unit, convertTemperature]);
  
  /**
   * Gets the temperature unit symbol
   * 
   * @returns Temperature unit symbol (°F or °C)
   */
  const getUnitSymbol = useCallback((): string => {
    return `°${unit}`;
  }, [unit]);
  
  return {
    unit,
    toCelsius,
    toFahrenheit,
    convertTemperature,
    formatTemperature,
    getUnitSymbol,
  };
};

export default useTemperatureUnit;
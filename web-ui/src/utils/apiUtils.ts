import type { SerializedError } from '@reduxjs/toolkit';
import type { FetchBaseQueryError } from '@reduxjs/toolkit/query';

/**
 * Checks if the error is a FetchBaseQueryError
 */
export function isFetchBaseQueryError(
  error: unknown
): error is FetchBaseQueryError {
  return typeof error === 'object' && error != null && 'status' in error;
}

/**
 * Checks if the error is a SerializedError
 */
export function isSerializedError(error: unknown): error is SerializedError {
  return (
    typeof error === 'object' &&
    error != null &&
    'message' in error &&
    'code' in error
  );
}

/**
 * Gets a readable error message from various error types
 */
export function getErrorMessage(error: unknown): string {
  if (isFetchBaseQueryError(error)) {
    // Handle FetchBaseQueryError
    if ('error' in error) {
      return typeof error.error === 'string' ? error.error : JSON.stringify(error.error);
    }
    
    if ('data' in error && error.data) {
      if (typeof error.data === 'string') {
        return error.data;
      }
      
      if (typeof error.data === 'object' && error.data !== null) {
        // Check for API error response formats
        if ('message' in error.data && typeof error.data.message === 'string') {
          return error.data.message;
        }
        
        if ('error' in error.data && typeof error.data.error === 'string') {
          return error.data.error;
        }
        
        // Standard error response
        if ('errors' in error.data && Array.isArray(error.data.errors)) {
          return error.data.errors.join(', ');
        }
      }
    }
    
    // Default status code message
    return `Error ${error.status}: Request failed`;
  } else if (isSerializedError(error)) {
    // Handle SerializedError
    return error.message || 'Unknown error occurred';
  } else if (error instanceof Error) {
    // Handle standard Error
    return error.message || 'Unknown error occurred';
  }
  
  // Fallback for unknown error types
  return 'An unknown error occurred';
}

/**
 * Formats API error response for use in UI
 */
export function formatApiError(error: unknown): string {
  return getErrorMessage(error);
}
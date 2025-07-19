import React, { createContext, useState, useContext, useEffect } from 'react';
import { useApi } from './ApiContext';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { apiCall } = useApi();

  // Check if user is already authenticated on app load
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('jwt_token');
      if (token) {
        try {
          const response = await apiCall('/api/auth/status', {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            }
          });

          if (response.ok) {
            const data = await response.json();
            if (data.status === 'success' && data.data.authenticated) {
              setUser(data.data.user);
            } else {
              localStorage.removeItem('jwt_token');
              localStorage.removeItem('session_token');
            }
          } else {
            localStorage.removeItem('jwt_token');
            localStorage.removeItem('session_token');
          }
        } catch (err) {
          console.error('Auth check failed:', err);
          localStorage.removeItem('jwt_token');
          localStorage.removeItem('session_token');
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, [apiCall]);

  const login = async (email, password) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiCall('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        const { user, jwt_token, session_token } = data.data;

        // Store tokens
        localStorage.setItem('jwt_token', jwt_token);
        localStorage.setItem('session_token', session_token);

        // Set user
        setUser(user);

        return { success: true, user };
      } else {
        const errorMessage = data.message || 'Login failed';
        setError(errorMessage);
        return { success: false, error: errorMessage };
      }
    } catch (err) {
      const errorMessage = 'Network error. Please try again.';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      const token = localStorage.getItem('jwt_token');
      const sessionToken = localStorage.getItem('session_token');

      if (token) {
        await apiCall('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Session-Token': sessionToken
          },
        });
      }
    } catch (err) {
      console.error('Logout API call failed:', err);
    } finally {
      // Clear local storage and state regardless of API call success
      localStorage.removeItem('jwt_token');
      localStorage.removeItem('session_token');
      setUser(null);
      setError(null);
    }
  };

  const register = async (email, password, name) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiCall('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password, name }),
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        return { success: true, user: data.data.user };
      } else {
        const errorMessage = data.message || 'Registration failed';
        setError(errorMessage);
        return { success: false, error: errorMessage };
      }
    } catch (err) {
      const errorMessage = 'Network error. Please try again.';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    loading,
    error,
    login,
    logout,
    register,
    setError,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

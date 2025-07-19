import React, { useState } from 'react';
import { loginUser } from '../utils/api';
import './Login.css';

const Login = ({ onLoginSuccess }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    login_type: 'thermoworks'
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [failedAttempts, setFailedAttempts] = useState(0);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Clear error when user starts typing
    if (error) {
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await loginUser(formData);

      if (response.status === 'success') {
        // Reset failed attempts on successful login
        setFailedAttempts(0);

        // Call parent callback with auth data
        onLoginSuccess(response.data);
      } else {
        throw new Error(response.message || 'Login failed');
      }
    } catch (err) {
      console.error('Login error:', err);

      // Track failed attempts
      setFailedAttempts(prev => prev + 1);

      // Set appropriate error message
      if (err.message.includes('rate limit') || err.message.includes('Too many')) {
        setError('Too many failed attempts. Please try again later.');
      } else if (err.message.includes('Invalid') || err.message.includes('credentials')) {
        setError('Invalid email or password. Please check your ThermoWorks Cloud credentials.');
      } else {
        setError(err.message || 'Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const isFormValid = formData.email && formData.password;

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>Grill Stats</h1>
          <p>ThermoWorks BBQ Monitoring</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">ThermoWorks Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="Enter your ThermoWorks Cloud email"
              required
              disabled={loading}
              className={error ? 'error' : ''}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Enter your ThermoWorks Cloud password"
              required
              disabled={loading}
              className={error ? 'error' : ''}
            />
          </div>

          <div className="form-group">
            <label htmlFor="login_type">Login Type</label>
            <select
              id="login_type"
              name="login_type"
              value={formData.login_type}
              onChange={handleChange}
              disabled={loading}
            >
              <option value="thermoworks">ThermoWorks Cloud</option>
              <option value="local">Local Account</option>
            </select>
          </div>

          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              {error}
              {failedAttempts >= 3 && (
                <div className="error-help">
                  <p>Need help? Make sure you're using your ThermoWorks Cloud credentials.</p>
                </div>
              )}
            </div>
          )}

          <button
            type="submit"
            className="login-button"
            disabled={!isFormValid || loading}
          >
            {loading ? (
              <span className="loading-text">
                <span className="spinner"></span>
                Signing in...
              </span>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="login-footer">
          <p>
            {formData.login_type === 'thermoworks' ?
              'Connect with your ThermoWorks Cloud account to access your devices.' :
              'Sign in with your local account.'
            }
          </p>

          <div className="login-help">
            <p>
              <strong>First time user?</strong> Use your ThermoWorks Cloud credentials to get started.
            </p>
            <p>
              <a href="https://cloud.thermoworks.com" target="_blank" rel="noopener noreferrer">
                Create ThermoWorks Cloud Account
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;

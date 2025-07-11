import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [isRegistering, setIsRegistering] = useState(false);
  const [registerData, setRegisterData] = useState({
    email: '',
    password: '',
    name: '',
  });
  const { login, register, loading, error } = useAuth();
  const navigate = useNavigate();

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleRegisterInputChange = (e) => {
    const { name, value } = e.target;
    setRegisterData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const result = await login(formData.email, formData.password);
    
    if (result.success) {
      navigate('/');
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    
    const result = await register(registerData.email, registerData.password, registerData.name);
    
    if (result.success) {
      setIsRegistering(false);
      setRegisterData({ email: '', password: '', name: '' });
      // Auto-login after registration
      await login(registerData.email, registerData.password);
      navigate('/');
    }
  };

  const toggleMode = () => {
    setIsRegistering(!isRegistering);
    setFormData({ email: '', password: '' });
    setRegisterData({ email: '', password: '', name: '' });
  };

  return (
    <div className="login-container">
      <div className="login-form">
        <h2>{isRegistering ? 'Create Account' : 'Welcome Back'}</h2>
        <p style={{ textAlign: 'center', marginBottom: '1.5rem', color: '#7f8c8d' }}>
          {isRegistering ? 'Sign up to manage your ThermoWorks devices' : 'Sign in to your ThermoWorks account'}
        </p>
        
        {error && <div className="error-message">{error}</div>}
        
        {!isRegistering ? (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                required
                placeholder="Enter your email"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                required
                placeholder="Enter your password"
              />
            </div>
            
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={loading}
              style={{ width: '100%', marginTop: '1rem' }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegisterSubmit}>
            <div className="form-group">
              <label htmlFor="name">Full Name</label>
              <input
                type="text"
                id="name"
                name="name"
                value={registerData.name}
                onChange={handleRegisterInputChange}
                required
                placeholder="Enter your full name"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={registerData.email}
                onChange={handleRegisterInputChange}
                required
                placeholder="Enter your email"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password"
                id="password"
                name="password"
                value={registerData.password}
                onChange={handleRegisterInputChange}
                required
                placeholder="Create a password"
                minLength="6"
              />
            </div>
            
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={loading}
              style={{ width: '100%', marginTop: '1rem' }}
            >
              {loading ? 'Creating Account...' : 'Create Account'}
            </button>
          </form>
        )}
        
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <p style={{ color: '#7f8c8d' }}>
            {isRegistering ? 'Already have an account?' : "Don't have an account?"}
          </p>
          <button 
            type="button" 
            onClick={toggleMode}
            className="btn btn-secondary"
            style={{ marginTop: '0.5rem' }}
          >
            {isRegistering ? 'Sign In' : 'Create Account'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
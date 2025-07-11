import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Header = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
  };

  const isActive = (path) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <header className="header" style={{ 
      display: 'flex', 
      justifyContent: 'space-between', 
      alignItems: 'center', 
      padding: '1rem 2rem',
      backgroundColor: '#2c3e50',
      color: 'white',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
        <h1 style={{ margin: 0, cursor: 'pointer' }} onClick={() => navigate('/')}>
          ThermoWorks Monitor
        </h1>
        <nav style={{ display: 'flex', gap: '1rem' }}>
          <button
            onClick={() => navigate('/devices')}
            style={{
              background: isActive('/devices') && !isActive('/devices/manage') ? '#34495e' : 'transparent',
              color: 'white',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.9rem'
            }}
          >
            Devices
          </button>
          <button
            onClick={() => navigate('/devices/manage')}
            style={{
              background: isActive('/devices/manage') ? '#34495e' : 'transparent',
              color: 'white',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.9rem'
            }}
          >
            Manage Devices
          </button>
          <button
            onClick={() => navigate('/sessions/history')}
            style={{
              background: isActive('/sessions/history') ? '#34495e' : 'transparent',
              color: 'white',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.9rem'
            }}
          >
            Session History
          </button>
        </nav>
      </div>
      <div className="user-info" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <span>Welcome, {user?.name || user?.email}</span>
        <button 
          onClick={handleLogout} 
          className="btn btn-secondary"
          style={{
            background: '#e74c3c',
            color: 'white',
            border: 'none',
            padding: '0.5rem 1rem',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
};

export default Header;
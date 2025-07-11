import React from 'react';
import { useAuth } from '../contexts/AuthContext';

const Header = () => {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <header className="header">
      <h1>ThermoWorks Monitor</h1>
      <div className="user-info">
        <span>Welcome, {user?.name || user?.email}</span>
        <button onClick={handleLogout} className="btn btn-secondary">
          Logout
        </button>
      </div>
    </header>
  );
};

export default Header;
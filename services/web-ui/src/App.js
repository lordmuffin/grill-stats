import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Login from './components/Login';
import DeviceList from './components/DeviceList';
import DeviceManagement from './components/DeviceManagement';
import LiveDeviceDashboard from './components/LiveDeviceDashboard';
import HistoricalGraph from './components/HistoricalGraph';
import HistoryPage from './components/HistoryPage';
import Header from './components/Header';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ApiProvider } from './contexts/ApiContext';

function App() {
  return (
    <AuthProvider>
      <ApiProvider>
        <Router>
          <div className="app">
            <AppContent />
          </div>
        </Router>
      </ApiProvider>
    </AuthProvider>
  );
}

function AppContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <>
      {user && <Header />}
      <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to="/" replace /> : <Login />}
        />
        <Route
          path="/"
          element={user ? <DeviceList /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/devices"
          element={user ? <DeviceList /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/devices/manage"
          element={user ? <DeviceManagement /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/devices/:deviceId/live"
          element={user ? <LiveDeviceDashboard /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/devices/:deviceId/history"
          element={user ? <HistoricalGraph /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/sessions/history"
          element={user ? <HistoryPage /> : <Navigate to="/login" replace />}
        />
        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
      </Routes>
    </>
  );
}

export default App;

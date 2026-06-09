import React from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Patients from './pages/Patients';
import History from './pages/History';
import Sidebar from './components/Sidebar';
import VoiceWidget from './components/VoiceWidget';

// Simple PrivateRoute wrapper checking localStorage
function PrivateRoute({ children }) {
  const auth = localStorage.getItem('isAuthenticated');
  return auth === 'true' ? children : <Navigate to="/login" />;
}

export default function App() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated');
    navigate('/login');
  };

  const isAuth = localStorage.getItem('isAuthenticated') === 'true';

  return (
    <div className="flex min-h-screen bg-gray-50">
      {isAuth && <Sidebar onLogout={handleLogout} />}
      {isAuth && <VoiceWidget />}
      
      <main className="flex-1 overflow-x-hidden overflow-y-auto">
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route path="/dashboard" element={
            <PrivateRoute><Dashboard /></PrivateRoute>
          } />
          
          <Route path="/patients" element={
            <PrivateRoute><Patients /></PrivateRoute>
          } />
          
          <Route path="/history" element={
            <PrivateRoute><History /></PrivateRoute>
          } />
          
          <Route path="/" element={<Navigate to={isAuth ? "/dashboard" : "/login"} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}

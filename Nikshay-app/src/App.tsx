import React, { useState, useEffect } from 'react';
import LoginPage from './components/auth/LoginPage';
import Layout from './components/layout/Layout';
import Dashboard from './components/dashboard/Dashboard';
import RequestService from './services/RequestService';

const App: React.FC = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [adminName, setAdminName] = useState('Admin User');
  
  // Check for existing login on component mount
  useEffect(() => {
    const loginStatus = localStorage.getItem('isLoggedIn');
    const storedAdminName = localStorage.getItem('adminName');
    
    if (loginStatus === 'true') {
      setIsLoggedIn(true);
      if (storedAdminName) {
        setAdminName(storedAdminName);
      }
    }
  }, []);

  // Login handler
  const handleLogin = (email: string, password: string) => {
    // Validate credentials
    if (email === 'admin@example.com' && password === 'admin123') {
      // Set display name based on email (in a real app, this would come from a user profile)
      const displayName = email.split('@')[0];
      const formattedName = displayName.charAt(0).toUpperCase() + displayName.slice(1);
      
      // Save login state to localStorage
      localStorage.setItem('isLoggedIn', 'true');
      localStorage.setItem('adminName', formattedName);
      
      // Update state
      setAdminName(formattedName);
      setIsLoggedIn(true);
      
      // Start email monitoring automatically
      RequestService.startMonitor().catch(err => {
        console.error('Failed to start email monitor:', err);
      });
      
      return true;
    }
    return false;
  };

  // Logout handler
  const handleLogout = () => {
    // Clear localStorage
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('adminName');
    
    // Update state
    setIsLoggedIn(false);
  };

  if (!isLoggedIn) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Layout adminName={adminName} onLogout={handleLogout}>
      <Dashboard />
    </Layout>
  );
};

export default App;

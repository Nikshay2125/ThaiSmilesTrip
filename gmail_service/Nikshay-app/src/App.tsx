import React, { useState, useEffect } from 'react';
import LoginPage from './components/auth/LoginPage';
import Layout from './components/layout/Layout';
import Dashboard from './components/dashboard/Dashboard';
import AuthService from './services/AuthService';

const App: React.FC = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [adminName, setAdminName] = useState('Admin User');
  
  // Check for existing login on component mount
  useEffect(() => {
    const checkAuth = () => {
      // Check if authenticated with AuthService
      if (AuthService.isAuthenticated()) {
        setIsLoggedIn(true);
        const user = AuthService.getUser();
        if (user) {
          setAdminName(user.name || user.sub.split('@')[0] || 'Admin User');
        }
        return;
      }
      
      // Fallback to localStorage for backward compatibility
      const loginStatus = localStorage.getItem('isLoggedIn');
      const storedAdminName = localStorage.getItem('adminName');
      
      if (loginStatus === 'true') {
        setIsLoggedIn(true);
        if (storedAdminName) {
          setAdminName(storedAdminName);
        }
      }
    };
    
    checkAuth();
    
    // Also check URL for token parameters (for Google OAuth callback)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('token')) {
      // Token will be handled by AuthService constructor
      checkAuth();
    }
  }, []);

  // Login handler
  const handleLogin = async (email: string, password: string): Promise<boolean> => {
    try {
      // Use AuthService for login
      const result = await AuthService.login(email, password);
      
      // Update state if login successful
      if (result) {
        const user = AuthService.getUser();
        if (user) {
          setAdminName(user.name || user.sub.split('@')[0] || 'Admin User');
        }
        setIsLoggedIn(true);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Login error:', error);
      return false;
    }
  };

  // Logout handler
  const handleLogout = () => {
    // Use AuthService for logout
    AuthService.logout();
    
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

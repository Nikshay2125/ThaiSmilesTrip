import React, { useState, useEffect } from 'react';
import { FiMail, FiLock, FiEye, FiEyeOff, FiLogIn } from 'react-icons/fi';
import { FcGoogle } from 'react-icons/fc';
import { FaFacebook, FaApple } from 'react-icons/fa';
import styles from '../../styles/components/LoginPage.module.scss';
import AuthService from '../../services/AuthService';

interface LoginPageProps {
  onLogin: (email: string, password: string) => boolean;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Check for token in URL (when returning from OAuth)
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    if (token) {
      // Process the token
      AuthService.handleAuthCallback(token);
      
      // Remove token from URL
      window.history.replaceState({}, document.title, window.location.pathname);
      
      // Trigger login in parent component
      onLogin('', '');
    }
  }, [onLogin]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    
    try {
      // Use AuthService for login
      const success = await AuthService.login(email, password);
      
      if (!success) {
        setError('Invalid credentials. Try admin@example.com / admin123');
      } else {
        // Call parent component's onLogin to update app state
        onLogin(email, password);
      }
    } catch (error) {
      setError('Login failed. Please try again later.');
      console.error('Login error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      setIsLoading(true);
      await AuthService.loginWithGoogle();
      // Redirect happens in the service
    } catch (error) {
      setError('Google login failed. Please try again later.');
      console.error('Google login error:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginBox}>
        <div className={styles.logo}>
          <FiLogIn />
        </div>

        <h1>Sign in to Dashboard</h1>
        <p className={styles.subtitle}>
          Manage booking requests and email confirmations
        </p>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && <div className={styles.errorMessage}>{error}</div>}
        
          <div className={styles.inputGroup}>
            <div className={styles.inputWrapper}>
              <FiMail className={styles.inputIcon} />
              <input
                type="email"
                placeholder="Email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </div>
          </div>

          <div className={styles.inputGroup}>
            <div className={styles.inputWrapper}>
              <FiLock className={styles.inputIcon} />
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="Password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
              />
              <button
                type="button"
                className={styles.passwordToggle}
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                disabled={isLoading}
              >
                {showPassword ? <FiEyeOff /> : <FiEye />}
              </button>
            </div>
          </div>

          <a href="#forgot" className={styles.forgotPassword}>
            Forgot password?
          </a>

          <button 
            type="submit" 
            className={styles.submitButton}
            disabled={isLoading}
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className={styles.divider}>
          <span>Or sign in with</span>
        </div>

        <div className={styles.socialButtons}>
          <button 
            type="button" 
            className={styles.socialButton} 
            aria-label="Sign in with Google"
            onClick={handleGoogleLogin}
            disabled={isLoading}
          >
            <FcGoogle />
          </button>
          <button 
            type="button" 
            className={styles.socialButton} 
            aria-label="Sign in with Facebook"
            disabled={isLoading || true} // Disabled until implemented
          >
            <FaFacebook />
          </button>
          <button 
            type="button" 
            className={styles.socialButton} 
            aria-label="Sign in with Apple"
            disabled={isLoading || true} // Disabled until implemented
          >
            <FaApple />
          </button>
        </div>
        
        <div className={styles.hint}>
          <small>Hint: Use admin@example.com / admin123</small>
        </div>
      </div>
    </div>
  );
};

export default LoginPage; 
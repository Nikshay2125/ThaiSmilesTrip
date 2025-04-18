import React, { useState } from 'react';
import { FiMail, FiLock, FiEye, FiEyeOff, FiLogIn } from 'react-icons/fi';
import { FcGoogle } from 'react-icons/fc';
import { FaFacebook, FaApple } from 'react-icons/fa';
import styles from '../../styles/components/LoginPage.module.scss';
import AuthService from '../../services/AuthService';

interface LoginPageProps {
  onLogin: (email: string, password: string) => Promise<boolean>;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    
    try {
      const success = await onLogin(email, password);
      
      if (!success) {
        setError('Invalid credentials. Try admin@example.com / admin123');
      }
    } catch (error) {
      console.error('Login error:', error);
      setError('Login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      setIsLoading(true);
      setError('');
      await AuthService.loginWithGoogle();
      // No need to do anything after the redirect - browser will navigate away
    } catch (err) {
      console.error('Google login error:', err);
      setError('Failed to connect with Google. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginBox}>
        <div className={styles.logo}>
          <FiLogIn />
        </div>

        <h1>Sign in with email</h1>
        <p className={styles.subtitle}>
          Make a new doc to bring your words, data,
          and teams together. For free
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
              />
              <button
                type="button"
                className={styles.passwordToggle}
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <FiEyeOff /> : <FiEye />}
              </button>
            </div>
          </div>

          <a href="#forgot" className={styles.forgotPassword}>
            Forgot password?
          </a>

          <button type="submit" className={styles.submitButton} disabled={isLoading}>
            Get Started
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
          <button type="button" className={styles.socialButton} aria-label="Sign in with Facebook" disabled={isLoading}>
            <FaFacebook />
          </button>
          <button type="button" className={styles.socialButton} aria-label="Sign in with Apple" disabled={isLoading}>
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
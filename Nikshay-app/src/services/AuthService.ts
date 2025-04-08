import axios from 'axios';
import RequestService from './RequestService';

const API_URL = 'http://localhost:5000/api';

interface UserInfo {
  sub: string;  // email
  name: string;
  picture?: string;
  exp?: number;
}

class AuthService {
  private token: string | null = null;
  private user: UserInfo | null = null;

  constructor() {
    // Check if token exists in localStorage
    this.token = localStorage.getItem('auth_token');
    const userStr = localStorage.getItem('user_info');
    if (userStr) {
      try {
        this.user = JSON.parse(userStr);
      } catch (e) {
        console.error('Failed to parse user info from localStorage');
      }
    }
  }

  async login(email: string, password: string): Promise<boolean> {
    // For demo/testing purposes - support the existing login in App.tsx
    if (email === 'admin@example.com' && password === 'admin123') {
      const mockUser = {
        sub: email,
        name: 'Admin',
        picture: null
      };
      
      // Store the mock user
      this.user = mockUser;
      localStorage.setItem('user_info', JSON.stringify(mockUser));
      localStorage.setItem('isLoggedIn', 'true');
      localStorage.setItem('adminName', 'Admin');
      
      return true;
    }
    
    return false;
  }

  async loginWithGoogle(): Promise<void> {
    try {
      // Request auth URL from backend
      const response = await axios.get(`${API_URL}/auth/google`);
      const { auth_url } = response.data;
      
      // Redirect to Google login
      window.location.href = auth_url;
    } catch (error) {
      console.error('Failed to initiate Google login', error);
      throw error;
    }
  }

  handleAuthCallback(token: string): void {
    if (token) {
      // Store token
      this.token = token;
      localStorage.setItem('auth_token', token);
      
      // Decode JWT to get user info (basic decode, no verification)
      try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
          atob(base64)
            .split('')
            .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
            .join('')
        );
        
        this.user = JSON.parse(jsonPayload);
        localStorage.setItem('user_info', JSON.stringify(this.user));
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('adminName', this.user.name);
        
        // Start email monitoring automatically
        RequestService.startMonitor().catch(err => {
          console.error('Failed to start email monitor:', err);
        });
      } catch (e) {
        console.error('Failed to decode JWT token', e);
      }
    }
  }

  logout(): void {
    this.token = null;
    this.user = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_info');
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('adminName');
  }

  getToken(): string | null {
    return this.token;
  }

  getUser(): UserInfo | null {
    return this.user;
  }

  isAuthenticated(): boolean {
    if (!this.token) return false;
    
    // Check if token is expired
    if (this.user?.exp) {
      const currentTime = Math.floor(Date.now() / 1000);
      if (this.user.exp < currentTime) {
        this.logout();
        return false;
      }
    }
    
    return true;
  }

  // Method to get axios instance with auth headers
  getAuthAxios() {
    const instance = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    // Add auth token to requests if available
    if (this.token) {
      instance.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
    }
    
    return instance;
  }
}

export default new AuthService(); 
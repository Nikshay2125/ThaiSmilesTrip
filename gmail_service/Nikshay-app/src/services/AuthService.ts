import axios from 'axios';

const API_URL = 'http://localhost:5000';

interface UserInfo {
  sub: string;  // email
  name: string;
  picture?: string | null;
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

    // Check for token in URL parameters (for OAuth callback)
    if (!this.token) {
      this.checkUrlForToken();
    }
  }

  checkUrlForToken() {
    // Extract token from URL if present (for OAuth callback)
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
      this.handleAuthCallback(token);
      
      // Clean URL by removing token parameter
      const url = new URL(window.location.href);
      url.searchParams.delete('token');
      window.history.replaceState({}, document.title, url.href);
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
      
      return Promise.resolve(true);
    }
    
    return Promise.resolve(false);
  }

  async loginWithGoogle(): Promise<void> {
    try {
      // Request auth URL from backend
      const response = await axios.get(`${API_URL}/auth/google`);
      const { auth_url } = response.data;
      
      // Redirect to Google login
      if (auth_url) {
        console.log('Redirecting to Google auth URL:', auth_url);
        window.location.href = auth_url;
      } else {
        throw new Error('No auth URL returned from server');
      }
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
        if (!base64Url) {
          throw new Error('Invalid token format');
        }
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
          atob(base64)
            .split('')
            .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
            .join('')
        );
        
        const decodedUser = JSON.parse(jsonPayload) as UserInfo;
        this.user = decodedUser;
        
        if (decodedUser && decodedUser.sub) {
          localStorage.setItem('user_info', JSON.stringify(decodedUser));
          localStorage.setItem('isLoggedIn', 'true');
          localStorage.setItem('adminName', decodedUser.name || decodedUser.sub);
        } else {
          throw new Error('Invalid user data in token');
        }
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
      baseURL: `${API_URL}/api`,
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
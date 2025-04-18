import AuthService from './AuthService';
import { io, Socket } from 'socket.io-client';

const API_URL = 'http://localhost:5000/api';

// Define the request interface based on our MongoDB schema
export interface EmailData {
  id: string;
  subject: string;
  from: string;
  date: string;
  body: string;
}

export interface ParsedData {
  date?: string;
  guest_name?: string;
  pax?: number;
  flight_no?: string;
  pickup_time?: string;
  pickup_location?: string;
  hotel_drop?: string;
  tour?: string;
  payment?: string;
  code?: string;
}

export interface Request {
  id: string;
  email_data: EmailData;
  parsed_data: ParsedData;
  status: 'pending' | 'confirmed' | 'rejected';
  created_at: string;
  confirmation_sent: boolean;
  user_email: string;
}

// Callback types for socket events
type RequestCallback = (request: Request) => void;
type RequestsCallback = (requests: Request[]) => void;

class RequestService {
  private socket: Socket | null = null;
  private callbacks: {
    newRequests: RequestsCallback[];
    requestUpdated: RequestCallback[];
  } = {
    newRequests: [],
    requestUpdated: []
  };
  
  // Add property to store the last error message
  public lastCheckErrorMessage: string | null = null;

  constructor() {
    // Initialize socket connection
    this.initSocket();
  }

  private initSocket() {
    // Create socket connection with reconnection options
    this.socket = io('http://localhost:5000', {
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 20000
    });

    // Setup event listeners
    this.socket.on('connect', () => {
      console.log('Socket connected');
      // Add auth token to socket connection
      const token = AuthService.getToken();
      if (token && this.socket) {
        this.socket.emit('authenticate', { token });
      }
    });

    this.socket.on('disconnect', (reason) => {
      console.log(`Socket disconnected: ${reason}`);
      if (reason === 'io server disconnect') {
        // The server has forcefully disconnected the socket
        // Try to reconnect manually
        console.log('Attempting to reconnect...');
        this.socket?.connect();
      }
    });

    this.socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
    });

    this.socket.on('reconnect', (attemptNumber) => {
      console.log(`Socket reconnected after ${attemptNumber} attempts`);
      // Re-authenticate on reconnection
      const token = AuthService.getToken();
      if (token && this.socket) {
        this.socket.emit('authenticate', { token });
      }
    });

    this.socket.on('reconnect_attempt', (attemptNumber) => {
      console.log(`Socket reconnection attempt ${attemptNumber}`);
    });

    this.socket.on('reconnect_error', (error) => {
      console.error('Socket reconnection error:', error);
    });

    this.socket.on('reconnect_failed', () => {
      console.error('Socket reconnection failed');
    });

    // Listen for new requests
    this.socket.on('new_requests', (data: { count: number, requests: Request[] }) => {
      console.log(`Received ${data.count} new requests`);
      this.callbacks.newRequests.forEach(callback => callback(data.requests));
    });

    // Listen for request updates
    this.socket.on('request_updated', (request: Request) => {
      console.log(`Request ${request.id} was updated`);
      this.callbacks.requestUpdated.forEach(callback => callback(request));
    });
    
    // Setup reload listener
    this.setupReloadListener();
  }

  // Add event listeners
  onNewRequests(callback: RequestsCallback) {
    this.callbacks.newRequests.push(callback);
  }

  onRequestUpdated(callback: RequestCallback) {
    this.callbacks.requestUpdated.push(callback);
  }

  // Remove event listeners
  offNewRequests(callback: RequestsCallback) {
    this.callbacks.newRequests = this.callbacks.newRequests.filter(cb => cb !== callback);
  }

  offRequestUpdated(callback: RequestCallback) {
    this.callbacks.requestUpdated = this.callbacks.requestUpdated.filter(cb => cb !== callback);
  }

  // Add socket event for reload_data
  setupReloadListener() {
    if (this.socket) {
      this.socket.on('reload_data', () => {
        console.log('Received reload_data event, fetching latest requests');
        // Use a try-catch block to handle potential errors
        try {
          this.getAllRequests()
            .then(requests => {
              console.log(`Reloaded ${requests.length} requests`);
              if (Array.isArray(requests)) {
                this.callbacks.newRequests.forEach(callback => callback(requests));
              } else {
                console.error('Unexpected response format from getAllRequests:', requests);
              }
            })
            .catch(error => {
              console.error('Error fetching requests on reload_data:', error);
            });
        } catch (error) {
          console.error('Error in reload_data handler:', error);
        }
      });
    }
  }

  // API Methods
  async getAllRequests(status?: string): Promise<Request[]> {
    try {
      const axios = AuthService.getAuthAxios();
      const params = status ? { status } : {};
      const response = await axios.get('/requests', { params });
      return response.data || [];
    } catch (error) {
      console.error('Error fetching requests:', error);
      return [];
    }
  }

  async getRequestById(id: string): Promise<Request | null> {
    try {
      const axios = AuthService.getAuthAxios();
      const response = await axios.get(`/requests/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching request ${id}:`, error);
      return null;
    }
  }

  async confirmRequest(id: string): Promise<Request | null> {
    try {
      const axios = AuthService.getAuthAxios();
      const response = await axios.post(`/requests/${id}/confirm`);
      return response.data.request;
    } catch (error) {
      console.error(`Error confirming request ${id}:`, error);
      return null;
    }
  }

  async updateRequestStatus(id: string, status: 'pending' | 'confirmed' | 'rejected'): Promise<Request | null> {
    try {
      const axios = AuthService.getAuthAxios();
      const response = await axios.put(`/requests/${id}/status`, { status });
      return response.data.request;
    } catch (error) {
      console.error(`Error updating request ${id} status:`, error);
      return null;
    }
  }

  async checkEmails(): Promise<Request[]> {
    try {
      const axios = AuthService.getAuthAxios();
      console.log('Sending request to check emails...');
      const response = await axios.post('/emails/check');
      console.log('Email check response:', response.data);
      
      // Store error message if any
      this.lastCheckErrorMessage = response.data.message || null;
      
      // If all_requests is provided, use it instead of just new_requests
      if (response.data.all_requests && Array.isArray(response.data.all_requests)) {
        console.log(`Received all ${response.data.all_requests.length} requests from email check`);
        // Notify listeners about ALL requests - wrap in try-catch to prevent crashes
        try {
          this.callbacks.newRequests.forEach(callback => callback(response.data.all_requests));
        } catch (error) {
          console.error('Error notifying callbacks about all_requests:', error);
        }
        return response.data.new_requests || [];
      }
      
      return response.data.new_requests || [];
    } catch (error) {
      console.error('Error checking emails:', error);
      this.lastCheckErrorMessage = 'Failed to connect to server';
      // Return empty array instead of throwing
      return [];
    }
  }

  async startMonitor(): Promise<boolean> {
    try {
      const axios = AuthService.getAuthAxios();
      await axios.post('/monitor/start');
      return true;
    } catch (error) {
      console.error('Error starting email monitor:', error);
      return false;
    }
  }

  async exportSpreadsheet(status?: string): Promise<boolean> {
    try {
      const axios = AuthService.getAuthAxios();
      const params = status ? { status } : {};
      const response = await axios.get('/export-spreadsheet', { 
        params,
        responseType: 'blob' 
      });
      
      // Create a URL for the blob
      const url = window.URL.createObjectURL(response.data);
      
      // Create a temporary link element
      const a = document.createElement('a');
      a.href = url;
      
      // Get filename from the content-disposition header if available
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'requests_export.xlsx';
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1];
        }
      }
      
      a.download = filename;
      
      // Trigger the download
      document.body.appendChild(a);
      a.click();
      
      // Clean up
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      return true;
    } catch (error) {
      console.error('Error exporting spreadsheet:', error);
      alert('Failed to export spreadsheet. Please try again later.');
      return false;
    }
  }
  
  // Cleanup method
  cleanup() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    
    this.callbacks.newRequests = [];
    this.callbacks.requestUpdated = [];
  }
}

export default new RequestService(); 
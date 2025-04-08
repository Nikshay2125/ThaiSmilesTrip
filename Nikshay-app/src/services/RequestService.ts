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
  confirmation: boolean;
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

  constructor() {
    // Initialize socket connection
    this.initSocket();
  }

  private initSocket() {
    // Create socket connection
    this.socket = io('http://localhost:5000');

    // Setup event listeners
    this.socket.on('connect', () => {
      console.log('Socket connected');
    });

    this.socket.on('disconnect', () => {
      console.log('Socket disconnected');
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

  // API Methods
  async getAllRequests(status?: string): Promise<Request[]> {
    try {
      const axios = AuthService.getAuthAxios();
      const params = status ? { status } : {};
      const response = await axios.get('/requests', { params });
      return response.data;
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
      const response = await axios.post('/emails/check');
      return response.data.new_requests || [];
    } catch (error) {
      console.error('Error checking emails:', error);
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

  async exportSpreadsheet(status?: string): Promise<void> {
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
      
    } catch (error) {
      console.error('Error exporting spreadsheet:', error);
      alert('Failed to export spreadsheet. Please try again later.');
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
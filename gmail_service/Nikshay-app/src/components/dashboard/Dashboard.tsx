import { useState, useEffect, useCallback, useRef } from 'react';
import { FiDownload } from 'react-icons/fi';
import styles from '../../styles/components/Dashboard.module.scss';
import RequestService, { Request } from '../../services/RequestService';
import RequestList from './RequestList';

const Dashboard = () => {
  const [isExporting, setIsExporting] = useState(false);
  const [requests, setRequests] = useState<Request[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // Safe state update function to prevent updates on unmounted component
  const safeSetState = <T extends unknown>(setter: React.Dispatch<React.SetStateAction<T>>) => 
    (value: React.SetStateAction<T>) => {
      if (mountedRef.current) {
        setter(value);
      }
    };

  const safeSetRequests = safeSetState(setRequests);
  const safeSetIsLoading = safeSetState(setIsLoading);
  const safeSetCheckError = safeSetState(setCheckError);
  const safeSetConnectionError = safeSetState(setConnectionError);
  const safeSetIsChecking = safeSetState(setIsChecking);

  const handleNewRequests = useCallback((newRequests: Request[]) => {
    console.log('New requests received:', newRequests);
    
    if (!Array.isArray(newRequests)) {
      console.error('Received invalid data for new requests, expected array but got:', typeof newRequests);
      return;
    }

    safeSetRequests(prev => {
      try {
        // Filter out any duplicates based on id
        if (!Array.isArray(prev)) {
          console.error('Previous state is not an array, resetting to empty array');
          return newRequests;
        }

        const existingIds = new Set(prev.map(r => r.id));
        const uniqueNewRequests = newRequests.filter(r => !existingIds.has(r.id));
        
        if (uniqueNewRequests.length > 0) {
          console.log(`Adding ${uniqueNewRequests.length} unique new requests`);
          return [...uniqueNewRequests, ...prev];
        }
        return prev;
      } catch (error) {
        console.error('Error handling new requests:', error);
        return prev; // Maintain existing state on error
      }
    });
  }, []);

  const handleRequestUpdate = useCallback((updatedRequest: Request) => {
    console.log('Request updated:', updatedRequest);
    
    if (!updatedRequest || !updatedRequest.id) {
      console.error('Received invalid update request:', updatedRequest);
      return;
    }

    safeSetRequests(prev => {
      try {
        if (!Array.isArray(prev)) {
          console.error('Previous state is not an array, resetting to empty array');
          return [updatedRequest];
        }
        
        return prev.map(req => 
          req.id === updatedRequest.id ? updatedRequest : req
        );
      } catch (error) {
        console.error('Error handling request update:', error);
        return prev; // Maintain existing state on error
      }
    });
  }, []);

  useEffect(() => {
    // Initial load of requests
    loadRequests();

    // Subscribe to new requests
    RequestService.onNewRequests(handleNewRequests);

    // Subscribe to request updates
    RequestService.onRequestUpdated(handleRequestUpdate);

    // Set mounted ref
    mountedRef.current = true;

    // Cleanup subscriptions and refs
    return () => {
      RequestService.cleanup();
      mountedRef.current = false;
    };
  }, [handleNewRequests, handleRequestUpdate]);

  const loadRequests = useCallback(async () => {
    safeSetIsLoading(true);
    safeSetConnectionError(null);
    
    try {
      const allRequests = await RequestService.getAllRequests();
      console.log('Loaded requests:', allRequests);
      
      if (Array.isArray(allRequests)) {
        safeSetRequests(allRequests);
      } else {
        console.error('Invalid response from getAllRequests:', allRequests);
        safeSetConnectionError('Received invalid data from server');
      }
    } catch (error) {
      console.error('Error loading requests:', error);
      safeSetConnectionError('Failed to load requests. Please refresh the page.');
    } finally {
      safeSetIsLoading(false);
    }
  }, []);

  const confirmRequest = useCallback(async (id: string) => {
    try {
      const updatedRequest = await RequestService.confirmRequest(id);
      if (updatedRequest) {
        console.log('Request confirmed:', updatedRequest);
        // Update the requests array with the confirmed request
        safeSetRequests(prev => {
          if (!Array.isArray(prev)) return prev;
          
          const updatedRequests = prev.map(req => 
            req.id === id ? {
              ...req,
              ...updatedRequest,
              status: 'confirmed' as 'pending' | 'confirmed' | 'rejected'  // Use type assertion for the status
            } : req
          );
          
          return updatedRequests;
        });
        
        // Show a success message
        if (mountedRef.current) {
          const successToast = document.createElement('div');
          successToast.className = styles.successToast;
          successToast.textContent = 'Request confirmed successfully!';
          document.body.appendChild(successToast);
          
          // Remove after 3 seconds
          setTimeout(() => {
            if (document.body.contains(successToast)) {
              document.body.removeChild(successToast);
            }
          }, 3000);
        }
      }
    } catch (error) {
      console.error(`Error confirming request ${id}:`, error);
      alert(`Failed to confirm request. Please try again.`);
    }
  }, []);

  const exportSpreadsheet = useCallback(async () => {
    try {
      setIsExporting(true);
      await RequestService.exportSpreadsheet();
    } catch (error) {
      console.error('Error exporting spreadsheet:', error);
      alert('Failed to export spreadsheet. Please try again later.');
    } finally {
      if (mountedRef.current) {
        setIsExporting(false);
      }
    }
  }, []);

  // Handle manual email check
  const checkEmails = useCallback(async () => {
    try {
      safeSetIsChecking(true);
      safeSetCheckError(null);
      console.log('Checking for new emails...');
      
      const newRequests = await RequestService.checkEmails();
      
      // The handling of new requests is now done in the RequestService via the callbacks
      // This is just for logging and error handling
      if (newRequests && newRequests.length > 0) {
        console.log(`Found ${newRequests.length} new requests from direct API call`);
      } else {
        console.log('No new requests found from direct API call');
        // Check for error message in the response
        if (RequestService.lastCheckErrorMessage) {
          safeSetCheckError(RequestService.lastCheckErrorMessage);
        }
      }
    } catch (error) {
      console.error('Error checking emails:', error);
      safeSetCheckError('Failed to check emails. Please try again later.');
    } finally {
      safeSetIsChecking(false);
    }
  }, []);

  return (
    <div className={styles.dashboard}>
      <div className={styles.dashboardHeader}>
        <h1 className={styles.title}>Dashboard</h1>
        <div className={styles.headerActions}>
          <button 
            className={styles.checkButton}
            onClick={checkEmails}
            disabled={isChecking}
          >
            {isChecking ? 'Checking...' : 'Check Now'}
          </button>
          <button 
            className={styles.exportButton} 
            onClick={exportSpreadsheet}
            disabled={isExporting}
          >
            <FiDownload /> {isExporting ? 'Exporting...' : 'Export Spreadsheet'}
          </button>
        </div>
      </div>

      {connectionError && (
        <div className={styles.errorMessage}>
          <strong>Connection Error:</strong> {connectionError}
          <button 
            className={styles.retryButton}
            onClick={loadRequests}
          >
            Retry
          </button>
        </div>
      )}

      {checkError && (
        <div className={styles.errorMessage}>
          {checkError}
        </div>
      )}

      <div className={styles.requestsSection}>
        <div className={styles.sectionHeader}>
          <h2>Requests</h2>
          <div className={styles.sectionActions}>
            <button 
              className={styles.refreshButton}
              onClick={loadRequests}
              disabled={isLoading}
            >
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
            <button className={styles.filterButton}>Filter</button>
          </div>
        </div>

        {isLoading ? (
          <div className={styles.loadingState}>Loading requests...</div>
        ) : requests.length === 0 ? (
          <div className={styles.emptyState}>No requests found</div>
        ) : (
          <RequestList 
            requests={requests}
            onConfirmRequest={confirmRequest}
          />
        )}
      </div>
    </div>
  );
};

export default Dashboard; 
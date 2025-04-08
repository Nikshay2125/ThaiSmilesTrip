import { useState, useEffect } from 'react';
import { FiChevronDown, FiChevronUp, FiCheck, FiDownload, FiX } from 'react-icons/fi';
import styles from '../../styles/components/Dashboard.module.scss';
import RequestService, { Request } from '../../services/RequestService';

const Dashboard = () => {
  const [expandedRequestId, setExpandedRequestId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [requests, setRequests] = useState<Request[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  // Fetch requests on component mount
  useEffect(() => {
    fetchRequests();

    // Set up socket listeners
    RequestService.onNewRequests(handleNewRequests);
    RequestService.onRequestUpdated(handleRequestUpdated);

    // Clean up on unmount
    return () => {
      RequestService.offNewRequests(handleNewRequests);
      RequestService.offRequestUpdated(handleRequestUpdated);
    };
  }, [statusFilter]);

  const handleNewRequests = (newRequests: Request[]) => {
    // Add new requests to the beginning of the list
    setRequests(prevRequests => {
      // Filter out any duplicates
      const newRequestIds = new Set(newRequests.map(req => req.id));
      const filteredCurrent = prevRequests.filter(req => !newRequestIds.has(req.id));
      
      return [...newRequests, ...filteredCurrent];
    });
  };

  const handleRequestUpdated = (updatedRequest: Request) => {
    // Update the request in our local state
    setRequests(prevRequests => 
      prevRequests.map(req => 
        req.id === updatedRequest.id ? updatedRequest : req
      )
    );
  };

  const fetchRequests = async () => {
    setIsLoading(true);
    try {
      const data = await RequestService.getAllRequests(statusFilter || undefined);
      setRequests(data);
    } catch (error) {
      console.error('Failed to fetch requests:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRequest = (id: string) => {
    setExpandedRequestId(expandedRequestId === id ? null : id);
  };

  const confirmRequest = async (id: string) => {
    try {
      const updatedRequest = await RequestService.confirmRequest(id);
      if (updatedRequest) {
        // Update the request in our local state
        setRequests(prevRequests => 
          prevRequests.map(req => 
            req.id === id ? updatedRequest : req
          )
        );
      }
    } catch (error) {
      console.error(`Failed to confirm request ${id}:`, error);
    }
  };

  const rejectRequest = async (id: string) => {
    try {
      const updatedRequest = await RequestService.updateRequestStatus(id, 'rejected');
      if (updatedRequest) {
        // Update the request in our local state
        setRequests(prevRequests => 
          prevRequests.map(req => 
            req.id === id ? updatedRequest : req
          )
        );
      }
    } catch (error) {
      console.error(`Failed to reject request ${id}:`, error);
    }
  };

  const exportSpreadsheet = async () => {
    try {
      setIsExporting(true);
      await RequestService.exportSpreadsheet(statusFilter || undefined);
    } catch (error) {
      console.error('Error exporting spreadsheet:', error);
      alert('Failed to export spreadsheet. Please try again later.');
    } finally {
      setIsExporting(false);
    }
  };

  const applyFilter = (status: string | null) => {
    setStatusFilter(status);
  };

  // Format date to a more readable format
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // Get status class for styling
  const getStatusClass = (status: string) => {
    switch (status) {
      case 'confirmed':
        return styles.statusConfirmed;
      case 'rejected':
        return styles.statusRejected;
      default:
        return styles.statusPending;
    }
  };

  return (
    <div className={styles.dashboard}>
      <div className={styles.dashboardHeader}>
        <h1 className={styles.title}>Dashboard</h1>
        <div className={styles.headerActions}>
          <button 
            className={styles.exportButton} 
            onClick={exportSpreadsheet}
            disabled={isExporting}
          >
            <FiDownload /> {isExporting ? 'Exporting...' : 'Export Spreadsheet'}
          </button>
        </div>
      </div>

      <div className={styles.requestsSection}>
        <div className={styles.sectionHeader}>
          <h2>Requests</h2>
          <div className={styles.filterButtons}>
            <button 
              className={`${styles.filterButton} ${statusFilter === null ? styles.activeFilter : ''}`}
              onClick={() => applyFilter(null)}
            >
              All
            </button>
            <button 
              className={`${styles.filterButton} ${statusFilter === 'pending' ? styles.activeFilter : ''}`}
              onClick={() => applyFilter('pending')}
            >
              Pending
            </button>
            <button 
              className={`${styles.filterButton} ${statusFilter === 'confirmed' ? styles.activeFilter : ''}`}
              onClick={() => applyFilter('confirmed')}
            >
              Confirmed
            </button>
            <button 
              className={`${styles.filterButton} ${statusFilter === 'rejected' ? styles.activeFilter : ''}`}
              onClick={() => applyFilter('rejected')}
            >
              Rejected
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className={styles.loadingState}>Loading requests...</div>
        ) : requests.length === 0 ? (
          <div className={styles.emptyState}>
            No requests found.
            {statusFilter && (
              <button 
                className={styles.clearFilterButton}
                onClick={() => setStatusFilter(null)}
              >
                Clear filter
              </button>
            )}
          </div>
        ) : (
        <div className={styles.requestList}>
          {requests.map((request) => (
            <div 
              key={request.id} 
              className={`${styles.requestItem} ${expandedRequestId === request.id ? styles.expanded : ''}`}
            >
              <div 
                className={styles.requestHeader}
                onClick={() => toggleRequest(request.id)}
              >
                <div className={styles.requestInfo}>
                  <span className={styles.requestId}>{request.id}</span>
                    <span className={styles.requestName}>
                      {request.parsed_data.guest_name || request.email_data.from.split('<')[0].trim()}
                    </span>
                    <span className={styles.requestDate}>
                      {formatDate(request.created_at)}
                    </span>
                    <span className={`${styles.requestStatus} ${getStatusClass(request.status)}`}>
                      {request.status.charAt(0).toUpperCase() + request.status.slice(1)}
                    </span>
                </div>
                <button className={styles.expandButton}>
                  {expandedRequestId === request.id ? <FiChevronUp /> : <FiChevronDown />}
                </button>
              </div>
              
              {expandedRequestId === request.id && (
                <div className={styles.requestDetails}>
                    <div className={styles.detailsContent}>
                      <div className={styles.detailsSection}>
                        <h3>Request Information</h3>
                        <p><strong>Subject:</strong> {request.email_data.subject}</p>
                        <p><strong>From:</strong> {request.email_data.from}</p>
                        <p><strong>Received:</strong> {request.email_data.date}</p>
                        <p><strong>Status:</strong> {request.status}</p>
                      </div>
                      
                      {Object.keys(request.parsed_data).length > 0 && (
                        <div className={styles.detailsSection}>
                          <h3>Booking Details</h3>
                          {request.parsed_data.guest_name && (
                            <p><strong>Guest:</strong> {request.parsed_data.guest_name}</p>
                          )}
                          {request.parsed_data.date && (
                            <p><strong>Date:</strong> {request.parsed_data.date}</p>
                          )}
                          {request.parsed_data.pax && (
                            <p><strong>Number of People:</strong> {request.parsed_data.pax}</p>
                          )}
                          {request.parsed_data.flight_no && (
                            <p><strong>Flight:</strong> {request.parsed_data.flight_no}</p>
                          )}
                          {request.parsed_data.pickup_time && (
                            <p><strong>Pickup Time:</strong> {request.parsed_data.pickup_time}</p>
                          )}
                          {request.parsed_data.pickup_location && (
                            <p><strong>Pickup Location:</strong> {request.parsed_data.pickup_location}</p>
                          )}
                          {request.parsed_data.hotel_drop && (
                            <p><strong>Hotel:</strong> {request.parsed_data.hotel_drop}</p>
                          )}
                          {request.parsed_data.code && (
                            <p><strong>Booking Code:</strong> {request.parsed_data.code}</p>
                          )}
                        </div>
                      )}
                      
                      <div className={styles.detailsSection}>
                        <h3>Email Content</h3>
                        <div className={styles.emailBody}>
                          {request.email_data.body}
                        </div>
                      </div>
                  </div>
                    
                  <div className={styles.requestActions}>
                      {request.status === 'pending' && (
                        <>
                    <button 
                      className={styles.confirmButton}
                      onClick={() => confirmRequest(request.id)}
                    >
                      <FiCheck /> Confirm
                    </button>
                          <button 
                            className={styles.rejectButton}
                            onClick={() => rejectRequest(request.id)}
                          >
                            <FiX /> Reject
                          </button>
                        </>
                      )}
                      {request.status === 'confirmed' && request.confirmation_sent && (
                        <div className={styles.statusBadge}>
                          <FiCheck /> Confirmation Email Sent
                        </div>
                      )}
                    </div>
                </div>
              )}
            </div>
          ))}
        </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard; 
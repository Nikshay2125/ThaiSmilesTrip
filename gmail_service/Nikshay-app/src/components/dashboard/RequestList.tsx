import React, { useState } from 'react';
import { FiChevronDown, FiChevronUp, FiCheck } from 'react-icons/fi';
import styles from '../../styles/components/Dashboard.module.scss';
import { Request } from '../../services/RequestService';

interface RequestListProps {
  requests: Request[];
  onConfirmRequest: (id: string) => Promise<void>;
}

const RequestList: React.FC<RequestListProps> = ({ requests, onConfirmRequest }) => {
  const [expandedRequestId, setExpandedRequestId] = useState<string | null>(null);
  const [confirmingIds, setConfirmingIds] = useState<Set<string>>(new Set());

  const toggleRequest = (id: string, e: React.MouseEvent) => {
    // Prevent the event from propagating up to parent elements
    e.preventDefault();
    e.stopPropagation();
    
    // Toggle the expanded state
    setExpandedRequestId(expandedRequestId === id ? null : id);
  };

  const handleConfirmRequest = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Mark this request as being confirmed
    setConfirmingIds(prev => {
      const newSet = new Set(prev);
      newSet.add(id);
      return newSet;
    });
    
    try {
      // Call the parent component's confirmation function
      await onConfirmRequest(id);
      
      // Request has been successfully confirmed
      // We keep it in the confirmingIds set to maintain the UI state
      // until the actual status update comes from the server
    } catch (error) {
      // On error, remove it from the confirming state
      console.error(`Error confirming request ${id}:`, error);
      setConfirmingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  return (
    <div className={styles.requestList}>
      {requests.map((request) => (
        <div 
          key={request.id} 
          className={`${styles.requestItem} ${expandedRequestId === request.id ? styles.expanded : ''}`}
        >
          <div 
            className={styles.requestHeader}
            onClick={(e) => toggleRequest(request.id, e)}
          >
            <div className={styles.requestInfo}>
              <span className={styles.requestId}>{request.id}</span>
              <span className={styles.requestName}>{request.email_data.from}</span>
              <span className={styles.requestDate}>{new Date(request.created_at).toLocaleDateString()}</span>
            </div>
            <div className={styles.headerControls}>
              {request.status === 'confirmed' && (
                <span className={styles.confirmedBadge}><FiCheck /> Confirmed</span>
              )}
              <button 
                className={styles.expandButton}
                onClick={(e) => toggleRequest(request.id, e)}
              >
                {expandedRequestId === request.id ? <FiChevronUp /> : <FiChevronDown />}
              </button>
            </div>
          </div>
          
          {expandedRequestId === request.id && (
            <div className={styles.requestDetails}>
              <div>
                <h3>{request.email_data.subject}</h3>
                <p><strong>Guest:</strong> {request.parsed_data?.guest_name || 'Guest name not available'}</p>
                <p><strong>PAX:</strong> {request.parsed_data?.pax || 'PAX not available'}</p>
                {request.parsed_data?.flight_no && <p><strong>Flight:</strong> {request.parsed_data.flight_no}</p>}
                {request.parsed_data?.pickup_time && <p><strong>Pickup Time:</strong> {request.parsed_data.pickup_time}</p>}
                {request.parsed_data?.pickup_location && <p><strong>Pickup Location:</strong> {request.parsed_data.pickup_location}</p>}
                {request.parsed_data?.hotel_drop && <p><strong>Hotel Drop:</strong> {request.parsed_data.hotel_drop}</p>}
                {request.parsed_data?.tour && <p><strong>Tour:</strong> {request.parsed_data.tour}</p>}
                <p><strong>Status:</strong> <span className={`${styles.statusBadge} ${styles[request.status]}`}>{request.status}</span></p>
              </div>
              <div className={styles.requestActions}>
                {request.status !== 'confirmed' ? (
                  <button 
                    className={`${styles.confirmButton} ${confirmingIds.has(request.id) ? styles.confirming : ''}`}
                    onClick={(e) => handleConfirmRequest(request.id, e)}
                    disabled={confirmingIds.has(request.id)}
                  >
                    <FiCheck /> {confirmingIds.has(request.id) ? 'Confirming...' : 'Confirm'}
                  </button>
                ) : (
                  <button 
                    className={`${styles.confirmedButton}`}
                    disabled={true}
                  >
                    <FiCheck /> Confirmed
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default RequestList; 
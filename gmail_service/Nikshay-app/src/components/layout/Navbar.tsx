import React from 'react';
import { FiMenu } from 'react-icons/fi';
import styles from '../../styles/components/Navbar.module.scss';
import sidebarStyles from '../../styles/components/Sidebar.module.scss';

interface NavbarProps {
  adminName: string;
  toggleSidebar: () => void;
  sidebarCollapsed: boolean;
}

const Navbar: React.FC<NavbarProps> = ({ adminName, toggleSidebar, sidebarCollapsed }) => {
  return (
    <header className={styles.header}>
      <button 
        className={sidebarStyles.toggleButton} 
        onClick={toggleSidebar}
        aria-label={sidebarCollapsed ? "Open sidebar" : "Close sidebar"}
      >
        <FiMenu />
      </button>
      <div className={`${styles.headerContent} ${sidebarCollapsed ? styles.headerFull : ''}`}>
        <div className={styles.logo}>
          Admin Panel
        </div>
        <div className={styles.welcome}>
          Welcome, {adminName}
        </div>
      </div>
    </header>
  );
};

export default Navbar; 
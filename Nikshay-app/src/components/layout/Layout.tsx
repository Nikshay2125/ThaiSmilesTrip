import React, { useState } from 'react';
import Navbar from './Navbar';
import Sidebar from './Sidebar';
import styles from '../../styles/components/Layout.module.scss';

interface LayoutProps {
  children: React.ReactNode;
  adminName: string;
  onLogout: () => void;
}

const Layout: React.FC<LayoutProps> = ({ children, adminName, onLogout }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  
  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  return (
    <div className={styles.layout}>
      <Navbar 
        adminName={adminName} 
        toggleSidebar={toggleSidebar} 
        sidebarCollapsed={sidebarCollapsed}
      />
      <div className={styles.container}>
        <Sidebar 
          onLogout={onLogout} 
          collapsed={sidebarCollapsed}
          toggleSidebar={toggleSidebar}
        />
        <main className={`${styles.main} ${sidebarCollapsed ? styles.mainFull : ''}`}>
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout; 
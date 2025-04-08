import React from 'react';
import { 
  FiGrid, 
  FiShoppingBag, 
  FiList,
  FiUsers,
  FiDollarSign,
  FiFileText,
  FiSettings,
  FiLogOut
} from 'react-icons/fi';
import styles from '../../styles/components/Sidebar.module.scss';

interface SidebarProps {
  onLogout: () => void;
  collapsed: boolean;
  toggleSidebar: () => void;
}

const menuItems = [
  { icon: FiGrid, label: 'Dashboard', href: '#' },
];

const Sidebar: React.FC<SidebarProps> = ({ onLogout, collapsed, toggleSidebar }) => {
  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ''}`}>
      
      <nav className={styles.navigation}>
        <ul>
          {menuItems.map((item, index) => (
            <li key={index} className={index === 0 ? styles.active : ''}>
              <a href={item.href}>
                <item.icon className={styles.icon} />
                <span className={styles.label}>{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className={styles.logoutSection}>
        <button className={styles.logoutButton} onClick={onLogout}>
          <FiLogOut className={styles.icon} />
          <span className={styles.label}>Log Out</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar; 
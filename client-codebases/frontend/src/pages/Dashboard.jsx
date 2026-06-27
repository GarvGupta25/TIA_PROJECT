import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { UploadCloud, Bell, MessageSquare, LogOut } from 'lucide-react';

const Dashboard = () => {
  const navigate = useNavigate();
  const userName = localStorage.getItem('user_name') || 'Client';

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '40px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'var(--accent-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontWeight: 'bold', fontSize: '18px', color: 'white' }}>C</span>
          </div>
          <div>
            <h2 style={{ fontSize: '16px', margin: 0, fontWeight: '600' }}>Client Portal</h2>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>Welcome, {userName}</p>
          </div>
        </div>

        <nav style={{ flex: 1 }}>
          <NavLink to="/dashboard/upload" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <UploadCloud size={20} />
            Upload Center
          </NavLink>
          <NavLink to="/dashboard/notifications" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Bell size={20} />
            Notifications
          </NavLink>
          <NavLink to="/dashboard/chat" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <MessageSquare size={20} />
            Messages
          </NavLink>
        </nav>

        <button 
          onClick={handleLogout}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px', cursor: 'pointer', borderRadius: '8px', transition: 'all 0.2s', width: '100%', textAlign: 'left', fontWeight: '500' }}
          onMouseOver={(e) => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)' }}
          onMouseOut={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'transparent' }}
        >
          <LogOut size={20} />
          Sign Out
        </button>
      </div>

      {/* Main Content Area */}
      <div className="main-content">
        <div className="animate-fade-in" style={{ height: '100%' }}>
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

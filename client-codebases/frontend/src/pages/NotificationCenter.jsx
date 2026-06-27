import React, { useState, useEffect } from 'react';
import { Bell, Info, CheckCircle, AlertTriangle } from 'lucide-react';

const NotificationCenter = () => {
  const [notifications, setNotifications] = useState([
    { id: 1, title: 'Invoice Approved', message: 'Your invoice INV-1002 has been successfully processed.', type: 'success', date: 'Just now' },
    { id: 2, title: 'New Employee Policy', message: 'Please review the updated HR policy regarding timesheet submissions.', type: 'info', date: '2 hours ago' },
    { id: 3, title: 'Missing Information', message: 'Excel file "Employees_May.xlsx" is missing the department column.', type: 'warning', date: '1 day ago' },
  ]);

  const getIcon = (type) => {
    switch(type) {
      case 'success': return <CheckCircle size={20} color="var(--success)" />;
      case 'warning': return <AlertTriangle size={20} color="var(--warning)" />;
      default: return <Info size={20} color="var(--accent-primary)" />;
    }
  };

  const getBg = (type) => {
    switch(type) {
      case 'success': return 'rgba(16, 185, 129, 0.1)';
      case 'warning': return 'rgba(245, 158, 11, 0.1)';
      default: return 'rgba(99, 102, 241, 0.1)';
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: '600', marginBottom: '8px' }}>Notification Center</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Stay updated with alerts and messages from the company.</p>
        </div>
        <button className="btn-secondary" style={{ fontSize: '14px', padding: '8px 16px' }}>Mark all as read</button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {notifications.map((notif) => (
          <div key={notif.id} className="glass-panel" style={{ padding: '20px', display: 'flex', gap: '20px', transition: 'transform 0.2s', cursor: 'pointer' }} onMouseOver={(e) => e.currentTarget.style.transform = 'translateX(4px)'} onMouseOut={(e) => e.currentTarget.style.transform = 'translateX(0)'}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: getBg(notif.type), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {getIcon(notif.type)}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                <h4 style={{ margin: 0, fontSize: '16px', fontWeight: '500' }}>{notif.title}</h4>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{notif.date}</span>
              </div>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '14px', lineHeight: '1.5' }}>{notif.message}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default NotificationCenter;

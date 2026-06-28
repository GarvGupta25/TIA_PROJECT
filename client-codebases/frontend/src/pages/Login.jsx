import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, User } from 'lucide-react';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

const Login = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('demo@client.com');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError('');
    setLoading(true);
    try {
      const body = new FormData();
      body.append('email', email);
      const { data } = await axios.post(`${API_BASE}/api/auth/login`, body);
      if (data.status !== 'success') {
        setError(data.message || 'Login failed');
        return;
      }
      localStorage.setItem('user_id', String(data.user_id));
      localStorage.setItem('user_name', data.name);
      localStorage.setItem('company_name', data.company_name || data.name);
      localStorage.setItem('client_code', data.client_code || 'CL004');
      navigate('/dashboard');
    } catch (err) {
      setError('Could not reach the client portal backend.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '420px', padding: '40px', textAlign: 'center' }}>
        <div style={{ marginBottom: '32px' }}>
          <div style={{ 
            width: '64px', height: '64px', borderRadius: '16px', 
            background: 'var(--accent-gradient)', margin: '0 auto 16px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 20px rgba(99, 102, 241, 0.4)'
          }}>
            <LogIn size={32} color="white" />
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: '600', marginBottom: '8px' }}>Client Login</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Demo account: demo@client.com</p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <input className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} />
          {error && <p style={{ color: 'var(--danger)', fontSize: '13px' }}>{error}</p>}
          <button className="btn-primary" onClick={handleLogin} style={{ width: '100%' }} disabled={loading}>
            <User size={18} />
            {loading ? 'Signing in...' : 'Login Demo Account'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import UploadCenter from './pages/UploadCenter';
import NotificationCenter from './pages/NotificationCenter';
import Chat from './pages/Chat';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        
        {/* Dashboard and its sub-pages */}
        <Route path="/dashboard" element={<Dashboard />}>
          <Route index element={<Navigate to="upload" replace />} />
          <Route path="upload" element={<UploadCenter />} />
          <Route path="notifications" element={<NotificationCenter />} />
          <Route path="chat" element={<Chat />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

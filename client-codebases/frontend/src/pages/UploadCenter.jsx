import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, Image as ImageIcon, Mail, Download } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

const uploadTypes = [
  { key: 'excel', label: 'Excel Files', accept: '.xlsx,.xls,.csv,.tsv', icon: FileText, description: 'Structured payroll sheets and exports.' },
  { key: 'photo', label: 'Photos', accept: '.png,.jpg,.jpeg,.webp,.bmp', icon: ImageIcon, description: 'Images of handwritten or printed timesheets.' },
  { key: 'email', label: 'PDF', accept: '.txt,.eml,.pdf', icon: Mail, description: 'PDF packs.' },
];

const UploadCenter = () => {
  const inputRef = useRef(null);
  const userId = localStorage.getItem('user_id') || '1';
  const companyName = localStorage.getItem('company_name') || 'Demo Client LLC';
  const [fileType, setFileType] = useState('excel');
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [returnedFiles, setReturnedFiles] = useState([]);

  const selectedType = uploadTypes.find((type) => type.key === fileType);

  const loadReturnedFiles = async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/api/returned/${userId}`);
      setReturnedFiles(data || []);
    } catch {
      setReturnedFiles([]);
    }
  };

  useEffect(() => {
    loadReturnedFiles();
  }, []);

  const addFiles = (fileList) => {
    const selected = Array.from(fileList || []).map((file) => ({ file, status: 'pending' }));
    setFiles((current) => [...current, ...selected]);
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setIsUploading(true);
    setMessage('');
    try {
      const body = new FormData();
      body.append('file_type', fileType);
      files.forEach((item) => body.append('files', item.file));
      const { data } = await axios.post(`${API_BASE}/api/upload/${userId}`, body);
      setFiles((current) => current.map((item) => ({ ...item, status: 'sent' })));
      setMessage(`${data.count} file(s) sent to TASC from ${companyName}.`);
    } catch {
      setMessage('Upload failed. Make sure the client backend is running.');
    } finally {
      setIsUploading(false);
      loadReturnedFiles();
    }
  };

  const getFileIcon = (file) => {
    if ((file.type || '').includes('image')) return <ImageIcon size={20} color="var(--accent-primary)" />;
    if (file.name.toLowerCase().endsWith('.eml') || file.name.toLowerCase().endsWith('.txt')) return <Mail size={20} color="var(--accent-primary)" />;
    return <FileText size={20} color="var(--accent-primary)" />;
  };

  return (
    <div style={{ maxWidth: '920px', margin: '0 auto' }}>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: '600', marginBottom: '8px' }}>Document Upload Center</h1>
        <p style={{ color: 'var(--text-secondary)' }}>{companyName} can send Excel, photo, email, and PDF files directly to TASC.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px', marginBottom: '20px' }}>
        {uploadTypes.map((type) => {
          const Icon = type.icon;
          return (
            <button
              key={type.key}
              className={`format-card ${fileType === type.key ? 'active' : ''}`}
              onClick={() => {
                setFileType(type.key);
                setFiles([]);
                setMessage('');
              }}
            >
              <Icon size={28} />
              <span style={{ color: 'var(--text-primary)', fontSize: '16px', fontWeight: 700 }}>{type.label}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '12px', lineHeight: 1.4 }}>{type.description}</span>
            </button>
          );
        })}
      </div>

      <div className="glass-panel upload-zone">
        <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'var(--primary-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
          <Upload size={32} color="var(--accent-primary)" />
        </div>
        <h3 style={{ fontSize: '18px', fontWeight: '500', marginBottom: '8px' }}>{selectedType.label}</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>Select one or more files, then send them to TASC.</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={selectedType.accept}
          style={{ display: 'none' }}
          onChange={(event) => addFiles(event.target.files)}
        />
        <button className="btn-secondary" style={{ margin: '0 auto' }} onClick={() => inputRef.current?.click()}>
          Browse Files
        </button>
      </div>

      {files.length > 0 && (
        <div style={{ marginTop: '28px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '500', marginBottom: '14px' }}>Selected Files</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {files.map((item, index) => (
              <div key={`${item.file.name}-${index}`} className="glass-panel file-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'var(--glass-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {getFileIcon(item.file)}
                  </div>
                  <div>
                    <p className="file-name" style={{ margin: 0 }}>{item.file.name}</p>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>{(item.file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                {item.status === 'sent' ? <CheckCircle size={20} color="var(--success)" /> : <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Pending</span>}
              </div>
            ))}
          </div>
          <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ color: message.includes('failed') ? 'var(--danger)' : 'var(--success)', fontSize: '14px' }}>{message}</p>
            <button className="btn-primary" onClick={handleUpload} disabled={isUploading || files.every((item) => item.status === 'sent')}>
              {isUploading ? 'Sending...' : 'Send to TASC'}
            </button>
          </div>
        </div>
      )}

      <div style={{ marginTop: '36px' }}>
        <h3 className="section-kicker" style={{ marginBottom: '14px' }}>Files From TASC</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {returnedFiles.length === 0 && <p style={{ color: 'var(--text-secondary)' }}>No files received from TASC yet.</p>}
          {returnedFiles.map((file) => (
            <div key={file.id} className="glass-panel file-card">
              <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
                <div className="icon-circle" style={{ background: 'var(--primary-glow)' }}><FileText size={20} color="var(--accent-primary)" /></div>
                <div>
                <p className="file-name" style={{ margin: 0 }}>{file.filename}</p>
                <p style={{ margin: '4px 0 0', color: 'var(--text-muted)', fontSize: '12px' }}>{file.note || 'Returned by TASC'}</p>
                </div>
              </div>
              <a className="btn-secondary" href={`${API_BASE}/api/returned/download/${file.id}`} target="_blank" rel="noreferrer">
                <Download size={16} />
                Download
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default UploadCenter;

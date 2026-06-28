import React, { useState, useEffect, useCallback } from 'react';
import { FileText, CheckCircle, Clock, AlertTriangle, RefreshCw, XCircle, ChevronDown, ChevronUp, Download } from 'lucide-react';
<<<<<<< HEAD
=======
import VoiceMicButton from '../components/VoiceMicButton';
import { useVoiceInput } from '../hooks/useVoiceInput';
>>>>>>> 83377e60 (smallest.ai integration)

const API_BASE = 'http://127.0.0.1:8001';

// Status priority for sorting: lower = shown first
const STATUS_PRIORITY = {
  CORRECTION_REQUESTED: 0,
  DISPUTED: 1,
  PENDING_APPROVAL: 2,
  APPROVED: 3,
};

const statusConfig = {
  PENDING_APPROVAL:    { label: 'Pending Approval',    color: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  border: 'rgba(245,158,11,0.25)',  Icon: Clock },
  APPROVED:            { label: 'Approved',             color: '#10B981', bg: 'rgba(16,185,129,0.10)',  border: 'rgba(16,185,129,0.25)',  Icon: CheckCircle },
  DISPUTED:            { label: 'Disputed',             color: '#EF4444', bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.25)',   Icon: XCircle },
  CORRECTION_REQUESTED:{ label: 'Correction Requested', color: '#F97316', bg: 'rgba(249,115,22,0.10)',  border: 'rgba(249,115,22,0.25)',  Icon: AlertTriangle },
};

function StatusBadge({ status }) {
  const cfg = statusConfig[status] || statusConfig.PENDING_APPROVAL;
  const { Icon } = cfg;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '4px 12px', borderRadius: '999px', fontSize: '12px', fontWeight: 700,
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`,
    }}>
      <Icon size={12} />
      {cfg.label}
    </span>
  );
}

function SummaryCard({ label, value, color, Icon }) {
  return (
    <div className="glass-panel" style={{ padding: '22px 24px', flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
            {label}
          </div>
          <div style={{ fontSize: '40px', fontWeight: 800, color: color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
            {value}
          </div>
        </div>
        <div style={{ width: 40, height: 40, borderRadius: '50%', display: 'grid', placeItems: 'center', background: `${color}22`, color }}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
}

// Line Items Table
function LineItemsTable({ lineItems }) {
  if (!lineItems || lineItems.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 13, padding: '8px 0' }}>No line-item details available.</p>;
  }
  return (
    <div style={{ overflowX: 'auto', marginTop: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Emp ID</th>
            <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Name</th>
            <th style={{ textAlign: 'right', padding: '8px 12px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Working Days</th>
            <th style={{ textAlign: 'right', padding: '8px 12px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Final Total</th>
          </tr>
        </thead>
        <tbody>
          {lineItems.map((item, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid rgba(30,45,64,0.5)' }}>
              <td style={{ padding: '8px 12px', fontFamily: 'var(--mono)', color: 'var(--text-primary)' }}>{item.emp_id}</td>
              <td style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>{item.full_name}</td>
              <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>{item.working_days}</td>
              <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700, color: 'var(--text-primary)' }}>AED {Number(item.final_total || 0).toLocaleString('en-AE', { minimumFractionDigits: 2 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Invoice Card
function InvoiceCard({ invoice, onRefresh }) {
  const [actionState, setActionState] = useState(null);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const isPending = invoice.status === 'PENDING_APPROVAL';
  const clientCode = localStorage.getItem('client_code') || 'CL004';

<<<<<<< HEAD
=======
  const handleTranscript = useCallback((text, isFinal) => {
    if (isFinal) {
      setInputText(prev => prev + (prev.endsWith(' ') || prev.length === 0 ? '' : ' ') + text + ' ');
    }
  }, []);

  const { isListening, interimTranscript, startListening, stopListening } = useVoiceInput(handleTranscript);

>>>>>>> 83377e60 (smallest.ai integration)
  let lineItems = [];
  try {
    lineItems = invoice.line_items ? JSON.parse(invoice.line_items) : [];
  } catch { lineItems = []; }

  const handleApprove = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/approve-invoice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invoice_id: invoice.invoice_id }),
      });
      setMsg({ type: 'success', text: 'Invoice approved successfully.' });
      setTimeout(() => { onRefresh(); }, 800);
    } catch {
      setMsg({ type: 'error', text: 'Failed to approve. Try again.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitDispute = async () => {
    if (!inputText.trim()) return;
    setLoading(true);
    const endpoint = actionState === 'dispute' ? '/dispute-invoice' : '/request-correction';
    const body = actionState === 'dispute'
      ? { invoice_id: invoice.invoice_id, client_code: clientCode, reason: inputText }
      : { invoice_id: invoice.invoice_id, client_code: clientCode, details: inputText };
    try {
      await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setMsg({ type: 'success', text: actionState === 'dispute' ? 'Dispute submitted.' : 'Correction request submitted.' });
      setActionState(null);
      setInputText('');
      setTimeout(() => { onRefresh(); }, 800);
    } catch {
      setMsg({ type: 'error', text: 'Submission failed. Try again.' });
    } finally {
      setLoading(false);
    }
  };

  const totalAmount = invoice.total_amount ? Number(invoice.total_amount) : null;

  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: 14, transition: 'all 200ms ease' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: 'var(--accent-primary)', marginBottom: 4 }}>
            {invoice.invoice_id}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{invoice.billing_period}</div>
        </div>
        <StatusBadge status={invoice.status} />
      </div>

      {/* Body */}
      <div style={{ display: 'flex', gap: 32, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Total Amount
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1 }}>
            {totalAmount !== null ? `AED ${totalAmount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}` : 'AED --'}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Dispatched
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
            {invoice.dispatched_at ? invoice.dispatched_at.slice(0, 16).replace('T', ' ') : '--'}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Employees
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
            {lineItems.length > 0 ? lineItems.length : '--'}
          </div>
        </div>
      </div>

      {invoice.dispatch_notes && (
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 14 }}>
          {invoice.dispatch_notes}
        </div>
      )}

      {/* Expandable line items */}
      {lineItems.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'none', border: '1px solid var(--border)', borderRadius: 8,
              color: 'var(--accent-primary)', fontSize: 13, fontWeight: 600, padding: '6px 14px',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {expanded ? 'Hide Details' : `View Details (${lineItems.length} employees)`}
          </button>
          {expanded && (
            <div style={{ marginTop: 8, padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <LineItemsTable lineItems={lineItems} />
            </div>
          )}
        </div>
      )}

      {/* PDF Download */}
      {invoice.pdf_path && (
        <div style={{ marginBottom: 14 }}>
          <a
            href={`${API_BASE}/invoice-pdf/${invoice.invoice_id}`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 13, fontWeight: 600, color: 'var(--accent-primary)',
              textDecoration: 'none', padding: '6px 14px',
              border: '1px solid var(--border)', borderRadius: 8,
            }}
          >
            <Download size={14} />
            Download Invoice PDF
          </a>
        </div>
      )}

      {/* Message */}
      {msg && (
        <div style={{ fontSize: 13, fontWeight: 600, color: msg.type === 'success' ? '#10B981' : '#EF4444', marginBottom: 12, padding: '8px 12px', borderRadius: 8, background: msg.type === 'success' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)' }}>
          {msg.text}
        </div>
      )}

      {/* Inline action input */}
      {actionState && (
        <div style={{ marginBottom: 14 }}>
<<<<<<< HEAD
          <textarea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            placeholder={actionState === 'dispute' ? 'Describe the reason for your dispute...' : 'Describe the correction needed...'}
            className="input-field"
            rows={3}
            style={{ resize: 'vertical', marginBottom: 8 }}
          />
=======
          <div style={{ position: 'relative' }}>
            <textarea
              value={isListening && interimTranscript ? inputText + (inputText.endsWith(' ') ? '' : ' ') + interimTranscript : inputText}
              onChange={e => setInputText(e.target.value)}
              placeholder={actionState === 'dispute' ? 'Describe the reason for your dispute...' : 'Describe the correction needed...'}
              className={`input-field ${isListening && interimTranscript ? 'voice-interim-text' : ''}`}
              rows={3}
              style={{ resize: 'vertical', marginBottom: 8, paddingRight: '40px', width: '100%' }}
              disabled={isListening}
            />
            <div style={{ position: 'absolute', top: '10px', right: '10px' }}>
              <VoiceMicButton 
                isListening={isListening} 
                onClick={isListening ? stopListening : startListening} 
              />
            </div>
          </div>
>>>>>>> 83377e60 (smallest.ai integration)
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn-primary"
              onClick={handleSubmitDispute}
              disabled={loading || !inputText.trim()}
              style={{ fontSize: 13, padding: '8px 16px' }}
            >
              {loading ? 'Submitting...' : actionState === 'dispute' ? 'Confirm Dispute' : 'Submit Correction'}
            </button>
            <button
              className="btn-secondary"
              onClick={() => { setActionState(null); setInputText(''); }}
              style={{ fontSize: 13, padding: '8px 16px' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Action buttons */}
      {!actionState && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            className="btn-primary"
            onClick={handleApprove}
            disabled={!isPending || loading}
            style={{ fontSize: 13, padding: '8px 16px', opacity: isPending ? 1 : 0.4, cursor: isPending ? 'pointer' : 'not-allowed' }}
          >
            <CheckCircle size={14} style={{ marginRight: 5 }} />
            Approve Invoice
          </button>
          <button
            className="btn-secondary"
            onClick={() => setActionState('dispute')}
            disabled={!isPending || loading}
            style={{ fontSize: 13, padding: '8px 16px', color: '#EF4444', borderColor: 'rgba(239,68,68,0.3)', opacity: isPending ? 1 : 0.4, cursor: isPending ? 'pointer' : 'not-allowed' }}
          >
            <XCircle size={14} style={{ marginRight: 5 }} />
            Dispute Invoice
          </button>
          <button
            className="btn-secondary"
            onClick={() => setActionState('correction')}
            disabled={!isPending || loading}
            style={{ fontSize: 13, padding: '8px 16px', color: '#F97316', borderColor: 'rgba(249,115,22,0.3)', opacity: isPending ? 1 : 0.4, cursor: isPending ? 'pointer' : 'not-allowed' }}
          >
            <AlertTriangle size={14} style={{ marginRight: 5 }} />
            Request Correction
          </button>
        </div>
      )}
    </div>
  );
}

// Main Page
export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const clientCode = localStorage.getItem('client_code') || 'CL004';

  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/client-invoices?client_code=${clientCode}`);
      if (!res.ok) throw new Error('Network error');
      const data = await res.json();
      // Sort: CORRECTION_REQUESTED first, DISPUTED next, PENDING_APPROVAL, then APPROVED
      data.sort((a, b) => (STATUS_PRIORITY[a.status] ?? 99) - (STATUS_PRIORITY[b.status] ?? 99));
      setInvoices(data);
    } catch (err) {
      setError('Could not load invoices. Make sure api.py is running on port 8001.');
    } finally {
      setLoading(false);
    }
  }, [clientCode]);

  useEffect(() => { fetchInvoices(); }, [fetchInvoices]);

  const total     = invoices.length;
  const awaiting  = invoices.filter(i => i.status === 'PENDING_APPROVAL').length;
  const approved  = invoices.filter(i => i.status === 'APPROVED').length;
  const actionReq = invoices.filter(i => i.status === 'CORRECTION_REQUESTED' || i.status === 'DISPUTED').length;

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', paddingBottom: 48 }}>
      {/* Page header */}
      <div style={{ marginBottom: 32 }}>
        <div className="section-kicker" style={{ marginBottom: 8 }}>Invoice Management</div>
        <h1>Invoice History</h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: 6, fontSize: 14 }}>
          Review and approve invoices sent by TASC
        </p>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 28, flexWrap: 'wrap' }}>
        <SummaryCard label="Total Received"    value={total}     color="var(--accent-primary)" Icon={FileText}      />
        <SummaryCard label="Awaiting Approval" value={awaiting}  color="var(--warning)"        Icon={Clock}         />
        <SummaryCard label="Action Required"   value={actionReq} color="var(--danger)"         Icon={AlertTriangle} />
        <SummaryCard label="Approved"          value={approved}  color="var(--success)"        Icon={CheckCircle}   />
      </div>

      {/* Refresh button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <button className="btn-secondary" onClick={fetchInvoices} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* State: loading / error / empty / list */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-secondary)' }}>
          Loading invoices...
        </div>
      )}
      {!loading && error && (
        <div className="glass-panel" style={{ padding: 24, color: '#EF4444', fontSize: 14 }}>
          {error}
        </div>
      )}
      {!loading && !error && invoices.length === 0 && (
        <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <FileText size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <p>No invoices received yet. TASC will push invoices here when they are ready.</p>
        </div>
      )}
      {!loading && !error && invoices.map(inv => (
        <InvoiceCard key={inv.invoice_id} invoice={inv} onRefresh={fetchInvoices} />
      ))}
    </div>
  );
}

import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Building } from 'lucide-react';

const Chat = () => {
  const [messages, setMessages] = useState([
    { id: 1, sender: 'company', text: 'Hello! Welcome to the client portal. How can we assist you today?', time: '10:00 AM' },
    { id: 2, sender: 'client', text: 'Hi, I just uploaded the new invoices. Can you confirm receipt?', time: '10:05 AM' },
    { id: 3, sender: 'company', text: 'Yes, we have received them. They are currently being processed by our system.', time: '10:07 AM' },
  ]);
  const [input, setInput] = useState('');
  const endOfMessagesRef = useRef(null);

  const scrollToBottom = () => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    const newMsg = {
      id: Date.now(),
      sender: 'client',
      text: input,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages([...messages, newMsg]);
    setInput('');
    
    // Simulate auto-reply
    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'company',
        text: 'Thank you for your message. An agent will review it shortly.',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    }, 1500);
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: '600', marginBottom: '8px' }}>Support Chat</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Communicate directly with our processing team.</p>
      </div>

      <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Chat Messages Area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {messages.map((msg) => {
            const isClient = msg.sender === 'client';
            return (
              <div key={msg.id} style={{ display: 'flex', gap: '12px', alignSelf: isClient ? 'flex-end' : 'flex-start', maxWidth: '75%' }}>
                {!isClient && (
                  <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <Building size={18} color="var(--text-secondary)" />
                  </div>
                )}
                
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: isClient ? 'flex-end' : 'flex-start' }}>
                  <div style={{ 
                    padding: '12px 16px', 
                    borderRadius: '16px',
                    borderBottomRightRadius: isClient ? '4px' : '16px',
                    borderBottomLeftRadius: !isClient ? '4px' : '16px',
                    background: isClient ? 'var(--accent-gradient)' : 'var(--glass-bg)',
                    border: isClient ? 'none' : '1px solid var(--glass-border)',
                    color: 'white',
                    fontSize: '15px',
                    lineHeight: '1.5'
                  }}>
                    {msg.text}
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{msg.time}</span>
                </div>

                {isClient && (
                  <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'rgba(99, 102, 241, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <User size={18} color="var(--accent-primary)" />
                  </div>
                )}
              </div>
            );
          })}
          <div ref={endOfMessagesRef} />
        </div>

        {/* Input Area */}
        <div style={{ padding: '20px', borderTop: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.2)' }}>
          <form onSubmit={handleSend} style={{ display: 'flex', gap: '12px' }}>
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..." 
              className="input-field" 
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn-primary" style={{ padding: '12px', width: '48px', height: '48px', borderRadius: '8px' }}>
              <Send size={20} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Chat;

import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Building } from 'lucide-react';

const Chat = () => {
  const [messages, setMessages] = useState([
    { id: 1, sender: 'company', text: 'Hello! Welcome to the client portal. How can we assist you today?', time: '10:00 AM' },
    { id: 2, sender: 'client', text: 'Hi, I just uploaded the new invoices. Can you confirm receipt?', time: '10:05 AM' },
    { id: 3, sender: 'company', text: 'Yes, we have received them. They are currently being processed by our system.', time: '10:07 AM' },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
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
    setIsTyping(true);
    
    // Simulate auto-reply
    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'company',
        text: 'Thank you for your message. An agent will review it shortly.',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
      setIsTyping(false);
    }, 1500);
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: '600', marginBottom: '8px' }}>Support Chat</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Communicate directly with our processing team.</p>
      </div>

      <div className="glass-panel chat-shell">
        {/* Chat Messages Area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {messages.map((msg) => {
            const isClient = msg.sender === 'client';
            return (
              <div key={msg.id} className={`chat-message ${isClient ? 'client' : 'system'}`} style={{ alignSelf: isClient ? 'flex-end' : 'flex-start' }}>
                {!isClient && (
                  <div className="icon-circle" style={{ width: '36px', height: '36px', background: 'var(--bg-elevated)' }}>
                    <Building size={18} color="var(--accent-secondary)" />
                  </div>
                )}
                
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: isClient ? 'flex-end' : 'flex-start' }}>
                  <div className="chat-bubble" style={{ borderBottomRightRadius: isClient ? '4px' : '16px', borderBottomLeftRadius: !isClient ? '4px' : '16px' }}>
                    {msg.text}
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{msg.time}</span>
                </div>

                {isClient && (
                  <div className="icon-circle" style={{ width: '36px', height: '36px', background: 'var(--primary-glow)' }}>
                    <User size={18} color="var(--accent-primary)" />
                  </div>
                )}
              </div>
            );
          })}
          {isTyping && (
            <div className="chat-message system" style={{ alignSelf: 'flex-start' }}>
              <div className="icon-circle" style={{ width: '36px', height: '36px', background: 'var(--bg-elevated)' }}>
                <Building size={18} color="var(--accent-secondary)" />
              </div>
              <div className="chat-bubble" style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          )}
          <div ref={endOfMessagesRef} />
        </div>

        {/* Input Area */}
        <div className="chat-input-bar">
          <form onSubmit={handleSend} style={{ display: 'flex', gap: '12px' }}>
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..." 
              className="input-field" 
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn-primary send-round">
              <Send size={20} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Chat;

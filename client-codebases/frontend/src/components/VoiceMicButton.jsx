import React from 'react';
import { Mic, MicOff } from 'lucide-react';

const VoiceMicButton = ({ isListening, onClick }) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`voice-mic-btn ${isListening ? 'listening' : ''}`}
      title={isListening ? "Stop listening" : "Start voice typing"}
    >
      {isListening ? (
        <MicOff size={20} color="var(--danger)" />
      ) : (
        <Mic size={20} color="var(--text-secondary)" />
      )}
      {isListening && <span className="listening-indicator" />}
    </button>
  );
};

export default VoiceMicButton;

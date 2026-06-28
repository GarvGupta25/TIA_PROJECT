import { useState, useRef, useCallback } from 'react';

export const useVoiceInput = (onTranscript) => {
  const [isListening, setIsListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);

  const stopListening = useCallback(() => {
    setIsListening(false);
    setInterimTranscript('');

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const startListening = useCallback(async () => {
    try {
      const ws = new WebSocket('ws://127.0.0.1:8500/ws/stt');
      wsRef.current = ws;

      ws.onopen = async () => {
        setIsListening(true);
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              channelCount: 1,
              sampleRate: 16000,
            }
          });
          mediaStreamRef.current = stream;

          const AudioContext = window.AudioContext || window.webkitAudioContext;
          const audioContext = new AudioContext({ sampleRate: 16000 });
          audioContextRef.current = audioContext;

          const source = audioContext.createMediaStreamSource(stream);
          const processor = audioContext.createScriptProcessor(4096, 1, 1);
          processorRef.current = processor;

          processor.onaudioprocess = (e) => {
            if (ws.readyState === WebSocket.OPEN) {
              const inputData = e.inputBuffer.getChannelData(0);
              // Convert Float32 to Int16
              const pcmData = new Int16Array(inputData.length);
              for (let i = 0; i < inputData.length; i++) {
                let s = Math.max(-1, Math.min(1, inputData[i]));
                pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
              }
              ws.send(pcmData.buffer);
            }
          };

          source.connect(processor);
          processor.connect(audioContext.destination);

        } catch (err) {
          console.error("Error accessing microphone:", err);
          stopListening();
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.error) {
            console.error("STT Error:", data.error);
            stopListening();
            return;
          }
          if (data.is_final) {
            onTranscript(data.transcript, true);
            setInterimTranscript('');
          } else {
            onTranscript(data.transcript, false);
            setInterimTranscript(data.transcript);
          }
        } catch (e) {
          // ignore parsing errors for non-json
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        stopListening();
      };

      ws.onclose = () => {
        stopListening();
      };

    } catch (err) {
      console.error("Error starting STT:", err);
      stopListening();
    }
  }, [onTranscript, stopListening]);

  return { isListening, interimTranscript, startListening, stopListening };
};

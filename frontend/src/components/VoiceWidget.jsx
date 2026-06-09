import React, { useState, useEffect } from 'react';
import Vapi from '@vapi-ai/web';
import { Mic, MicOff, Loader2 } from 'lucide-react';

const vapi = new Vapi(import.meta.env.VITE_VAPI_CLIENT_KEY);
const assistantId = import.meta.env.VITE_VAPI_ASSISTANT_ID;

export default function VoiceWidget() {
  const [callStatus, setCallStatus] = useState('idle'); // idle, loading, active

  useEffect(() => {
    vapi.on('call-start', () => setCallStatus('active'));
    vapi.on('call-end', () => setCallStatus('idle'));
    vapi.on('error', (e) => {
      console.error(e);
      setCallStatus('idle');
    });
    
    // Cleanup listeners on unmount
    return () => {
      vapi.removeAllListeners('call-start');
      vapi.removeAllListeners('call-end');
      vapi.removeAllListeners('error');
    };
  }, []);

  const toggleCall = async () => {
    if (!assistantId || assistantId === 'your_assistant_id_here') {
      alert('Please configure your VITE_VAPI_ASSISTANT_ID in the frontend environment variables to start the call.');
      return;
    }

    if (callStatus === 'idle') {
      setCallStatus('loading');
      try {
        await vapi.start(assistantId);
      } catch (err) {
        console.error('Failed to start Vapi call:', err);
        setCallStatus('idle');
      }
    } else {
      vapi.stop();
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 group">
      <button
        onClick={toggleCall}
        className={`relative flex h-16 w-16 items-center justify-center rounded-full shadow-2xl transition-all duration-300 hover:scale-105 active:scale-95 ${
          callStatus === 'active'
            ? 'bg-rose-500 hover:bg-rose-600'
            : callStatus === 'loading'
            ? 'bg-amber-500 cursor-wait'
            : 'bg-emerald-500 hover:bg-emerald-600'
        }`}
        title={callStatus === 'active' ? 'End Call' : 'Call Assistant'}
      >
        {/* Pulsing rings for active state */}
        {callStatus === 'active' && (
          <>
            <span className="absolute inset-0 rounded-full bg-rose-400 opacity-75 animate-ping" style={{ animationDuration: '2s' }}></span>
            <span className="absolute inset-0 rounded-full bg-rose-400 opacity-50 animate-ping" style={{ animationDuration: '1.5s', animationDelay: '0.2s' }}></span>
          </>
        )}
        
        {/* Icon */}
        <div className="relative z-10 text-white">
          {callStatus === 'active' ? (
            <MicOff size={28} />
          ) : callStatus === 'loading' ? (
            <Loader2 size={28} className="animate-spin" />
          ) : (
            <Mic size={28} />
          )}
        </div>
      </button>
      
      {/* Tooltip */}
      <div className="absolute bottom-20 right-0 w-32 text-center text-sm font-medium text-slate-700 bg-white px-3 py-2 rounded-lg shadow-xl opacity-0 transition-opacity duration-300 pointer-events-none group-hover:opacity-100">
        {callStatus === 'active' ? 'End Call' : 'Test Assistant'}
      </div>
    </div>
  );
}

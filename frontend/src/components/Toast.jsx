import React, { useEffect } from 'react';
import { AlertCircle, X } from 'lucide-react';

export default function Toast({ message, onClose }) {
  useEffect(() => {
    // Play beep sound for critical alert
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
      console.error("Audio playback failed", e);
    }

    const timer = setTimeout(onClose, 5000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="fixed bottom-4 right-4 bg-red-600 text-white px-6 py-4 rounded-lg shadow-xl flex items-center gap-4 animate-bounce z-50">
      <AlertCircle className="w-6 h-6 animate-pulse" />
      <div>
        <h4 className="font-bold">CRITICAL ALERT</h4>
        <p className="text-sm">{message}</p>
      </div>
      <button onClick={onClose} className="ml-4 text-red-200 hover:text-white">
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { User, Phone, Globe, Activity, X } from 'lucide-react';
import { API_BASE } from '../config';


export default function Patients() {
  const [patients, setPatients] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [voiceInput, setVoiceInput] = useState('');
  const [simResult, setSimResult] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/patients`)
      .then(res => res.json())
      .then(data => setPatients(data))
      .catch(e => console.error(e));
  }, []);

  const handleSimulate = async () => {
    try {
      // In a real app, we'd send the voice text to an NLP engine.
      // Here we map a simple text to an intent and symptoms.
      const lower = voiceInput.toLowerCase();
      let symptoms = [];
      let severity = "low";
      if (lower.includes('chest') || lower.includes('breathe')) {
        symptoms = ["chest_pain", "breathing_problem"];
        severity = "critical";
      } else if (lower.includes('fall') || lower.includes('fell')) {
        symptoms = ["fall_detected"];
        severity = "high";
      } else if (lower.includes('dizzy')) {
        symptoms = ["dizziness"];
        severity = "medium";
      } else if (lower.includes('pill') || lower.includes('medicine')) {
        symptoms = ["medicine_missed"];
        severity = "low";
      }

      const res = await fetch(`${API_BASE}/assess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intent: "health_issue",
          symptoms,
          severity,
          confidence: 0.9
        })
      });
      const data = await res.json();
      setSimResult(data);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-2xl font-bold text-gray-800">Patients</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {patients.map(p => (
          <div key={p.id} className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="bg-teal-600 h-24 relative">
              <div className="absolute -bottom-10 left-6 bg-white p-2 rounded-full border-4 border-white shadow-sm">
                <div className="bg-teal-100 p-4 rounded-full">
                  <User className="w-8 h-8 text-teal-700" />
                </div>
              </div>
            </div>
            <div className="pt-14 px-6 pb-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">{p.name}</h3>
                  <p className="text-gray-500">Age: {p.age}</p>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded-full">
                  {p.status}
                </span>
              </div>
              
              <div className="space-y-3 text-sm text-gray-600 mb-6">
                <div className="flex gap-2">
                  <Activity className="w-4 h-4 text-gray-400 shrink-0" />
                  <span>{p.conditions.join(', ')}</span>
                </div>
                <div className="flex gap-2">
                  <Phone className="w-4 h-4 text-gray-400 shrink-0" />
                  <span>{p.emergency_contact}</span>
                </div>
                <div className="flex gap-2">
                  <Globe className="w-4 h-4 text-gray-400 shrink-0" />
                  <span>{p.language}</span>
                </div>
              </div>

              <button 
                onClick={() => setIsModalOpen(true)}
                className="w-full py-2 bg-teal-50 text-teal-700 font-medium rounded hover:bg-teal-100 transition"
              >
                Simulate Voice Input
              </button>
            </div>
          </div>
        ))}
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Simulate Voice Input</h3>
              <button onClick={() => { setIsModalOpen(false); setSimResult(null); setVoiceInput(''); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <p className="text-sm text-gray-500 mb-4">Type what the patient said (e.g., "I have chest pain", "I feel dizzy").</p>
            
            <textarea
              className="w-full border border-gray-300 rounded p-3 mb-4 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
              rows="4"
              value={voiceInput}
              onChange={(e) => setVoiceInput(e.target.value)}
              placeholder="Start typing..."
            />
            
            <button 
              onClick={handleSimulate}
              className="w-full py-2 bg-teal-600 text-white font-medium rounded hover:bg-teal-700 transition mb-4"
            >
              Analyze
            </button>

            {simResult && (
              <div className={`p-4 rounded border ${simResult.risk_level === 'CRITICAL' ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'}`}>
                <h4 className="font-bold text-sm mb-2">Result:</h4>
                <div className="text-sm space-y-1">
                  <p><strong>Risk:</strong> {simResult.risk_level} (Score: {simResult.score})</p>
                  <p><strong>Action:</strong> {simResult.action}</p>
                  <p><strong>Message:</strong> {simResult.message}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

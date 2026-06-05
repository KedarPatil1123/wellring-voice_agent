import React, { useState, useEffect } from 'react';
import StatsCard from '../components/StatsCard';
import AlertCard from '../components/AlertCard';
import Toast from '../components/Toast';
import { mockAssessments } from '../mockAssessments';
import { Mic, Activity, RefreshCw } from 'lucide-react';
import { API_BASE } from '../config';


export default function Dashboard() {
  const [isConnected, setIsConnected] = useState(false);
  const [stats, setStats] = useState({ total_today: 0, low: 0, medium: 0, high: 0, critical: 0 });
  const [assessments, setAssessments] = useState(mockAssessments);
  const [criticalToast, setCriticalToast] = useState(null);

  // Poll Health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) setIsConnected(true);
        else setIsConnected(false);
      } catch (e) {
        setIsConnected(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  // Poll Stats & Assessments
  useEffect(() => {
    const fetchData = async () => {
      if (!isConnected) return;
      try {
        const [statsRes, assRes] = await Promise.all([
          fetch(`${API_BASE}/assessments/stats`),
          fetch(`${API_BASE}/assessments?limit=10`)
        ]);
        
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
        
        if (assRes.ok) {
          const assData = await assRes.json();
          if (assData && assData.length > 0) {
            // Check for new critical
            const latestNew = assData[0];
            const latestOld = assessments[0];
            if (latestNew.id !== latestOld?.id && latestNew.risk_level === 'CRITICAL') {
              setCriticalToast(`New CRITICAL alert for ${latestNew.patient_name || 'Mr. Sharma'}!`);
            }
            setAssessments(assData);
          }
        }
      } catch (e) {
        console.error("Failed fetching data", e);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [isConnected, assessments]);

  const simulateEmergency = async () => {
    try {
      await fetch(`${API_BASE}/assess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intent: "health_issue",
          symptoms: ["chest_pain", "breathing_problem"],
          severity: "critical",
          confidence: 0.95
        })
      });
    } catch (e) {
      console.error("Failed to simulate", e);
    }
  };

  return (
    <div className="p-8">
      {criticalToast && <Toast message={criticalToast} onClose={() => setCriticalToast(null)} />}
      
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-2xl font-bold text-gray-800">Dashboard Overview</h2>
        <div className="flex items-center gap-4">
          <button 
            onClick={simulateEmergency}
            className="flex items-center gap-2 bg-red-100 text-red-700 px-4 py-2 rounded-lg font-medium hover:bg-red-200 transition"
          >
            <Activity className="w-4 h-4" />
            Simulate Emergency
          </button>
          <div className="flex items-center gap-2 px-3 py-1 bg-white rounded-full shadow-sm border text-sm font-medium">
            <span className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            {isConnected ? 'API Connected' : 'API Offline'}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        <StatsCard title="Total Today" value={stats.total_today} colorClass="#9ca3af" />
        <StatsCard title="Low Risk" value={stats.low} colorClass="#9ca3af" />
        <StatsCard title="Medium Risk" value={stats.medium} colorClass="#eab308" />
        <StatsCard title="High Risk" value={stats.high} colorClass="#f97316" />
        <StatsCard title="Critical Risk" value={stats.critical} colorClass="#ef4444" />
      </div>

      <div className="bg-white rounded-xl shadow-sm border p-6">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Activity className="w-5 h-5 text-teal-600" />
            Live Alert Feed
          </h3>
          <span className="text-sm text-gray-500 flex items-center gap-1">
            <RefreshCw className="w-3 h-3 animate-spin" /> Auto-updating
          </span>
        </div>
        
        {assessments.length === 0 ? (
          <div className="text-center py-12 flex flex-col items-center">
            <div className="bg-teal-50 p-4 rounded-full mb-4">
              <Mic className="w-8 h-8 text-teal-600" />
            </div>
            <p className="text-gray-500 text-lg">Waiting for voice input...</p>
          </div>
        ) : (
          <div className="max-h-[600px] overflow-y-auto pr-2">
            {assessments.map(a => (
              <AlertCard key={a.id || Math.random()} assessment={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

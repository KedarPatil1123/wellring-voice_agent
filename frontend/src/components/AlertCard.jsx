import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react';

export default function AlertCard({ assessment }) {
  const isCritical = assessment.risk_level === 'CRITICAL';
  
  const riskColors = {
    LOW: 'bg-gray-100 text-gray-800 border-gray-300',
    MEDIUM: 'bg-yellow-50 text-yellow-800 border-yellow-300',
    HIGH: 'bg-orange-50 text-orange-800 border-orange-300',
    CRITICAL: 'bg-red-50 text-red-800 border-red-500'
  };

  const riskIcons = {
    LOW: <Info className="w-5 h-5 text-gray-500" />,
    MEDIUM: <CheckCircle className="w-5 h-5 text-yellow-500" />,
    HIGH: <AlertTriangle className="w-5 h-5 text-orange-500" />,
    CRITICAL: <AlertCircle className="w-5 h-5 text-red-600 animate-pulse" />
  };

  const timeString = new Date(assessment.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className={`p-4 rounded-lg shadow-sm border mb-4 flex items-start gap-4 transition-all duration-300 ${isCritical ? 'border-l-8 border-red-600 animate-pulse bg-red-50' : 'bg-white'}`}>
      <div className="flex-shrink-0 mt-1">
        {riskIcons[assessment.risk_level] || <Info className="w-5 h-5" />}
      </div>
      <div className="flex-grow">
        <div className="flex justify-between items-start">
          <div>
            <h4 className={`font-semibold ${isCritical ? 'text-red-900 font-bold' : 'text-gray-900'}`}>
              {assessment.patient_name || 'Mr. Sharma'}
            </h4>
            <span className="text-sm text-gray-500">{timeString}</span>
          </div>
          <div className="flex gap-2">
            <span className={`px-2 py-1 text-xs font-semibold rounded-full border ${riskColors[assessment.risk_level]}`}>
              {assessment.risk_level}
            </span>
            <span className="px-2 py-1 text-xs font-semibold bg-gray-100 text-gray-600 rounded-full border">
              Score: {assessment.score}
            </span>
          </div>
        </div>
        <div className="mt-2 text-sm text-gray-700">
          <p><strong>Symptoms:</strong> {Array.isArray(assessment.symptoms) ? assessment.symptoms.join(', ') : assessment.symptoms}</p>
          <p className="mt-1"><strong>Action:</strong> {assessment.action.replace(/_/g, ' ')}</p>
        </div>
      </div>
    </div>
  );
}

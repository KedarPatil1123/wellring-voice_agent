import React, { useState, useEffect } from 'react';
import { Download, Search, Filter } from 'lucide-react';
import { mockAssessments } from '../mockAssessments';

const API_BASE = 'http://localhost:8000';

export default function History() {
  const [assessments, setAssessments] = useState(mockAssessments);
  const [search, setSearch] = useState('');
  const [filterRisk, setFilterRisk] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/assessments?limit=100`)
      .then(res => res.json())
      .then(data => {
        if(data && data.length > 0) setAssessments(data);
      })
      .catch(e => console.error(e));
  }, []);

  const filtered = assessments.filter(a => {
    const symps = Array.isArray(a.symptoms) ? a.symptoms.join(' ') : a.symptoms;
    const matchesSearch = symps?.toLowerCase().includes(search.toLowerCase()) || 
                          a.patient_name?.toLowerCase().includes(search.toLowerCase());
    const matchesRisk = filterRisk ? a.risk_level === filterRisk : true;
    return matchesSearch && matchesRisk;
  });

  const exportCsv = () => {
    const headers = ['ID', 'Time', 'Patient', 'Symptoms', 'Risk', 'Score', 'Action'];
    const rows = filtered.map(a => [
      a.id,
      new Date(a.timestamp).toLocaleString(),
      a.patient_name || 'Mr. Sharma',
      Array.isArray(a.symptoms) ? a.symptoms.join(';') : a.symptoms,
      a.risk_level,
      a.score,
      a.action
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'assessments.csv';
    link.click();
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-2xl font-bold text-gray-800">Assessment History</h2>
        <button 
          onClick={exportCsv}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="p-4 border-b flex gap-4 bg-gray-50">
          <div className="relative flex-1">
            <Search className="w-5 h-5 absolute left-3 top-2.5 text-gray-400" />
            <input 
              type="text" 
              placeholder="Search symptoms or patient name..." 
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-teal-500"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="relative w-48">
            <Filter className="w-5 h-5 absolute left-3 top-2.5 text-gray-400" />
            <select 
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-teal-500 appearance-none bg-white"
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
            >
              <option value="">All Risks</option>
              <option value="LOW">Low Risk</option>
              <option value="MEDIUM">Medium Risk</option>
              <option value="HIGH">High Risk</option>
              <option value="CRITICAL">Critical Risk</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-gray-700 border-b">
              <tr>
                <th className="px-6 py-3 font-medium">Time</th>
                <th className="px-6 py-3 font-medium">Patient</th>
                <th className="px-6 py-3 font-medium">Symptoms</th>
                <th className="px-6 py-3 font-medium">Risk Level</th>
                <th className="px-6 py-3 font-medium">Score</th>
                <th className="px-6 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(a => (
                <tr key={a.id || Math.random()} className="border-b hover:bg-gray-50 transition">
                  <td className="px-6 py-4 whitespace-nowrap">{new Date(a.timestamp).toLocaleString()}</td>
                  <td className="px-6 py-4 font-medium text-gray-900">{a.patient_name || 'Mr. Sharma'}</td>
                  <td className="px-6 py-4">{Array.isArray(a.symptoms) ? a.symptoms.join(', ') : a.symptoms}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-semibold rounded-full border ${
                      a.risk_level === 'CRITICAL' ? 'bg-red-50 text-red-800 border-red-300' :
                      a.risk_level === 'HIGH' ? 'bg-orange-50 text-orange-800 border-orange-300' :
                      a.risk_level === 'MEDIUM' ? 'bg-yellow-50 text-yellow-800 border-yellow-300' :
                      'bg-gray-100 text-gray-800 border-gray-300'
                    }`}>
                      {a.risk_level}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-semibold">{a.score}</td>
                  <td className="px-6 py-4 truncate max-w-xs" title={a.action}>{a.action.replace(/_/g, ' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="p-8 text-center text-gray-500">
              No assessments found matching the criteria.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

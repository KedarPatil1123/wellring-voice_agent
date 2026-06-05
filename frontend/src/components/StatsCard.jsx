import React from 'react';

export default function StatsCard({ title, value, colorClass }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 border-l-4" style={{ borderColor: colorClass || '#0f766e' }}>
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">{title}</h3>
      <p className="mt-2 text-3xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}

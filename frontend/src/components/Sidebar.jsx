import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, Users, Clock, LogOut } from 'lucide-react';

export default function Sidebar({ onLogout }) {
  const navItems = [
    { to: '/dashboard', icon: <Activity className="w-5 h-5" />, label: 'Dashboard' },
    { to: '/patients', icon: <Users className="w-5 h-5" />, label: 'Patients' },
    { to: '/history', icon: <Clock className="w-5 h-5" />, label: 'History' },
  ];

  return (
    <div className="w-64 bg-teal-800 text-white flex flex-col h-screen">
      <div className="p-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="w-8 h-8" />
          WellRing
        </h1>
        <p className="text-teal-200 text-sm mt-1">Caregiver Portal</p>
      </div>
      
      <nav className="flex-1 mt-6">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-6 py-4 transition-colors ${
                isActive ? 'bg-teal-900 border-l-4 border-white' : 'hover:bg-teal-700 border-l-4 border-transparent'
              }`
            }
          >
            {item.icon}
            <span className="font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-teal-700">
        <button 
          onClick={onLogout}
          className="flex items-center gap-3 px-4 py-2 w-full text-teal-200 hover:text-white hover:bg-teal-700 rounded transition-colors"
        >
          <LogOut className="w-5 h-5" />
          <span>Log out</span>
        </button>
      </div>
    </div>
  );
}

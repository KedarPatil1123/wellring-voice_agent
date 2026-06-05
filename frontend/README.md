# WellRing Caregiver Dashboard

A React application built with Vite, Tailwind CSS, and React Router to serve as the caregiver portal for the WellRing voice health monitoring system.

## Features
- **Live Feed**: Connects to the FastAPI backend to display real-time voice assessments.
- **Visual Risk Alerts**: Critical symptoms automatically pulse and show clear warnings.
- **Simulation Mode**: Test emergency workflows and symptom matching directly from the UI.
- **Export**: History page supports simple CSV exports.

## Getting Started

### Prerequisites
- Node.js installed

### Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Open `http://localhost:5173` in your browser.

> **Login:** Use username `caregiver` and password `wellring` to log in.

*Note: Make sure the FastAPI backend is running on `http://localhost:8000` for live data fetching to work.*

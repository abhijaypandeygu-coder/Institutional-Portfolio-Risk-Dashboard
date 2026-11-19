import { LiveUpdatesProvider } from './hooks/useLiveRefresh';
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { App } from './App';
import { ComponentCanvas } from './components/ComponentCanvas';
const showCanvas = import.meta.env.DEV && new URLSearchParams(window.location.search).has('canvas');

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <LiveUpdatesProvider>{showCanvas ? <ComponentCanvas /> : <App />}</LiveUpdatesProvider>
  </React.StrictMode>
);

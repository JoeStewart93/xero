import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { App } from './App';
import { AuthProvider } from './auth';
import { C2ConnectionProvider } from './c2Connection';
import { TaskCompletionNotifier } from './components/TaskCompletionNotifier';
import { RealtimeProvider } from './realtime';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <C2ConnectionProvider>
        <AuthProvider>
          <RealtimeProvider>
            <App />
            <TaskCompletionNotifier />
          </RealtimeProvider>
        </AuthProvider>
      </C2ConnectionProvider>
    </BrowserRouter>
  </React.StrictMode>,
);

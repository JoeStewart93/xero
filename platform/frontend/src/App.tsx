import { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { HealthPage } from './pages/HealthPage';
import { BeaconsPage } from './pages/BeaconsPage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ReconPage } from './pages/ReconPage';
import { SettingsPage } from './pages/SettingsPage';
import { useAuth } from './useAuth';

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  if (!session) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<Navigate to="/home" replace />} />
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recon"
        element={
          <ProtectedRoute>
            <ReconPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons"
        element={
          <ProtectedRoute>
            <BeaconsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/health"
        element={
          <ProtectedRoute>
            <HealthPage />
          </ProtectedRoute>
        }
      />
      <Route path="/settings/health" element={<Navigate to="/health" replace />} />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

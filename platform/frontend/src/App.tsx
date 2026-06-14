import { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { BeaconWorkspacePage, BeaconWorkspaceRedirectPage } from './pages/BeaconWorkspacePage';
import { BeaconsSessionsPage } from './pages/BeaconsSessionsPage';
import { HealthPage } from './pages/HealthPage';
import { BeaconsDeployPage } from './pages/BeaconsDeployPage';
import { BeaconsPage } from './pages/BeaconsPage';
import { C2SettingsPage } from './pages/C2SettingsPage';
import { GroupingRulesPage } from './pages/GroupingRulesPage';
import { HomePage } from './pages/HomePage';
import { InventoryPage } from './pages/InventoryPage';
import { LoginPage } from './pages/LoginPage';
import { ModulesPage } from './pages/ModulesPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PlannedSectionPage } from './pages/PlannedSectionPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectsScopePage, ProjectsScopeRedirectPage } from './pages/ProjectsScopePage';
import { ReconPage } from './pages/ReconPage';
import { SettingsPage } from './pages/SettingsPage';
import { StubSectionPage } from './pages/StubSectionPage';
import { TrafficPatternsPage } from './pages/TrafficPatternsPage';
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
      <Route path="/inventory" element={<Navigate to="/assets" replace />} />
      <Route path="/module-catalog" element={<Navigate to="/modules" replace />} />
      <Route path="/reporting" element={<Navigate to="/reports" replace />} />
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route path="/home/activity" element={<Navigate to="/home" replace />} />
      <Route path="/home/actions" element={<Navigate to="/home" replace />} />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/scope"
        element={
          <ProtectedRoute>
            <ProjectsScopeRedirectPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/scope"
        element={
          <ProtectedRoute>
            <ProjectsScopePage />
          </ProtectedRoute>
        }
      />
      <Route path="/projects/timeline" element={<Navigate to="/projects" replace />} />
      <Route path="/projects/team" element={<Navigate to="/projects" replace />} />
      <Route
        path="/recon"
        element={
          <ProtectedRoute>
            <ReconPage />
          </ProtectedRoute>
        }
      />
      <Route path="/recon/runs" element={<Navigate to="/recon" replace />} />
      <Route path="/recon/results" element={<Navigate to="/recon" replace />} />
      <Route path="/recon/activity" element={<Navigate to="/recon" replace />} />
      <Route
        path="/beacons"
        element={
          <ProtectedRoute>
            <BeaconsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons/sessions"
        element={
          <ProtectedRoute>
            <BeaconsSessionsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/beacons/groups" element={<Navigate to="/beacons" replace />} />
      <Route path="/beacons/profiles" element={<Navigate to="/payloads/traffic-patterns" replace />} />
      <Route
        path="/beacons/deploy"
        element={
          <ProtectedRoute>
            <BeaconsDeployPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons/:beaconId"
        element={
          <ProtectedRoute>
            <BeaconWorkspaceRedirectPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons/:beaconId/:operation"
        element={
          <ProtectedRoute>
            <BeaconWorkspacePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exploits"
        element={
          <ProtectedRoute>
            <PlannedSectionPage section="exploits" />
          </ProtectedRoute>
        }
      />
      <Route path="/exploits/*" element={<Navigate to="/exploits" replace />} />
      <Route path="/payloads" element={<Navigate to="/payloads/traffic-patterns" replace />} />
      <Route path="/payloads/encrypter" element={<Navigate to="/payloads/traffic-patterns" replace />} />
      <Route path="/payloads/obfuscator" element={<Navigate to="/payloads/traffic-patterns" replace />} />
      <Route
        path="/payloads/traffic-patterns"
        element={
          <ProtectedRoute>
            <TrafficPatternsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/payloads/traffic-shaping" element={<Navigate to="/payloads/traffic-patterns" replace />} />
      <Route path="/payloads/output" element={<Navigate to="/payloads/traffic-patterns" replace />} />
      <Route
        path="/assets"
        element={
          <ProtectedRoute>
            <InventoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/modules"
        element={
          <ProtectedRoute>
            <ModulesPage />
          </ProtectedRoute>
        }
      />
      <Route path="/assets/*" element={<Navigate to="/assets" replace />} />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <PlannedSectionPage section="reports" />
          </ProtectedRoute>
        }
      />
      <Route path="/reports/*" element={<Navigate to="/reports" replace />} />
      <Route
        path="/loot"
        element={
          <ProtectedRoute>
            <PlannedSectionPage section="loot" />
          </ProtectedRoute>
        }
      />
      <Route path="/loot/*" element={<Navigate to="/loot" replace />} />
      <Route
        path="/health"
        element={
          <ProtectedRoute>
            <HealthPage />
          </ProtectedRoute>
        }
      />
      <Route path="/health/live" element={<Navigate to="/health" replace />} />
      <Route path="/settings/health" element={<Navigate to="/health" replace />} />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/settings/profiles" element={<Navigate to="/payloads/traffic-patterns?profiles=1" replace />} />
      <Route
        path="/settings/grouping"
        element={
          <ProtectedRoute>
            <GroupingRulesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings/api-keys"
        element={
          <ProtectedRoute>
            <StubSectionPage section="settings" tabId="api-keys" />
          </ProtectedRoute>
        }
      />
      <Route path="/settings/access" element={<Navigate to="/settings" replace />} />
      <Route path="/settings/bff" element={<Navigate to="/settings" replace />} />
      <Route path="/settings/plugins" element={<Navigate to="/settings" replace />} />
      <Route path="/settings/notifications" element={<Navigate to="/settings" replace />} />
      <Route
        path="/settings/infrastructure"
        element={
          <ProtectedRoute>
            <C2SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/settings/c2" element={<Navigate to="/settings/infrastructure" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

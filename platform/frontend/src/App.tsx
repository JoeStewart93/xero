import { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

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
import { ProjectsPage } from './pages/ProjectsPage';
import { ReconPage } from './pages/ReconPage';
import { SettingsPage } from './pages/SettingsPage';
import { StubSectionPage } from './pages/StubSectionPage';
import { TrafficProfilesPage } from './pages/TrafficProfilesPage';
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
      <Route
        path="/home/activity"
        element={
          <ProtectedRoute>
            <StubSectionPage section="home" tabId="activity-feed" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/home/actions"
        element={
          <ProtectedRoute>
            <StubSectionPage section="home" tabId="quick-actions" />
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
        path="/projects/scope"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/timeline"
        element={
          <ProtectedRoute>
            <StubSectionPage section="projects" tabId="timeline" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/team"
        element={
          <ProtectedRoute>
            <StubSectionPage section="projects" tabId="team" />
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
        path="/recon/runs"
        element={
          <ProtectedRoute>
            <StubSectionPage section="recon" tabId="runs" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recon/results"
        element={
          <ProtectedRoute>
            <StubSectionPage section="recon" tabId="results" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recon/activity"
        element={
          <ProtectedRoute>
            <StubSectionPage section="recon" tabId="activity" />
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
        path="/beacons/sessions"
        element={
          <ProtectedRoute>
            <StubSectionPage section="beacons" tabId="sessions" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons/groups"
        element={
          <ProtectedRoute>
            <StubSectionPage section="beacons" tabId="groups" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons/profiles"
        element={
          <ProtectedRoute>
            <StubSectionPage section="beacons" tabId="profiles" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/beacons/deploy"
        element={
          <ProtectedRoute>
            <BeaconsDeployPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exploits"
        element={
          <ProtectedRoute>
            <StubSectionPage section="exploits" tabId="browser" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exploits/suggestions"
        element={
          <ProtectedRoute>
            <StubSectionPage section="exploits" tabId="suggestions" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exploits/execution"
        element={
          <ProtectedRoute>
            <StubSectionPage section="exploits" tabId="execution" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exploits/results"
        element={
          <ProtectedRoute>
            <StubSectionPage section="exploits" tabId="results" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/payloads"
        element={
          <ProtectedRoute>
            <StubSectionPage section="payloads" tabId="generator" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/payloads/encrypter"
        element={
          <ProtectedRoute>
            <StubSectionPage section="payloads" tabId="encrypter" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/payloads/obfuscator"
        element={
          <ProtectedRoute>
            <StubSectionPage section="payloads" tabId="obfuscator" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/payloads/traffic-shaping"
        element={
          <ProtectedRoute>
            <StubSectionPage section="payloads" tabId="traffic-shaping" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/payloads/output"
        element={
          <ProtectedRoute>
            <StubSectionPage section="payloads" tabId="output" />
          </ProtectedRoute>
        }
      />
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
      <Route
        path="/assets/hosts"
        element={
          <ProtectedRoute>
            <StubSectionPage section="assets" tabId="hosts" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets/services"
        element={
          <ProtectedRoute>
            <StubSectionPage section="assets" tabId="services" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets/vulnerabilities"
        element={
          <ProtectedRoute>
            <StubSectionPage section="assets" tabId="vulnerabilities" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets/domains"
        element={
          <ProtectedRoute>
            <StubSectionPage section="assets" tabId="domains" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets/cloud-resources"
        element={
          <ProtectedRoute>
            <StubSectionPage section="assets" tabId="cloud-resources" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets/relationships"
        element={
          <ProtectedRoute>
            <StubSectionPage section="assets" tabId="relationships" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <StubSectionPage section="reports" tabId="notes" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports/campaign"
        element={
          <ProtectedRoute>
            <StubSectionPage section="reports" tabId="campaign-reports" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports/hosts"
        element={
          <ProtectedRoute>
            <StubSectionPage section="reports" tabId="host-reports" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports/vulnerabilities"
        element={
          <ProtectedRoute>
            <StubSectionPage section="reports" tabId="vulnerability-reports" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports/exports"
        element={
          <ProtectedRoute>
            <StubSectionPage section="reports" tabId="exports" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/loot"
        element={
          <ProtectedRoute>
            <StubSectionPage section="loot" tabId="credentials" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/loot/files"
        element={
          <ProtectedRoute>
            <StubSectionPage section="loot" tabId="files" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/loot/secrets"
        element={
          <ProtectedRoute>
            <StubSectionPage section="loot" tabId="secrets" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/loot/quick-save"
        element={
          <ProtectedRoute>
            <StubSectionPage section="loot" tabId="quick-save" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/loot/search"
        element={
          <ProtectedRoute>
            <StubSectionPage section="loot" tabId="search" />
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
      <Route
        path="/health/live"
        element={
          <ProtectedRoute>
            <StubSectionPage section="health" tabId="liveness" />
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
      <Route
        path="/settings/profiles"
        element={
          <ProtectedRoute>
            <TrafficProfilesPage />
          </ProtectedRoute>
        }
      />
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
      <Route
        path="/settings/access"
        element={
          <ProtectedRoute>
            <StubSectionPage section="settings" tabId="access" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings/bff"
        element={
          <ProtectedRoute>
            <StubSectionPage section="settings" tabId="bff" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings/plugins"
        element={
          <ProtectedRoute>
            <StubSectionPage section="settings" tabId="plugins" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings/notifications"
        element={
          <ProtectedRoute>
            <StubSectionPage section="settings" tabId="notifications" />
          </ProtectedRoute>
        }
      />
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

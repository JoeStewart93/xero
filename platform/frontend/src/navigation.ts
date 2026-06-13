import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  Boxes,
  Cable,
  Crosshair,
  FileArchive,
  FolderKanban,
  HeartPulse,
  Home,
  KeyRound,
  Layers3,
  ListChecks,
  RadioTower,
  Settings,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';

export type ShellSection =
  | 'assets'
  | 'beacons'
  | 'exploits'
  | 'health'
  | 'home'
  | 'loot'
  | 'payloads'
  | 'projects'
  | 'recon'
  | 'reports'
  | 'settings';

export interface NavItem {
  enabled: boolean;
  icon: LucideIcon;
  label: string;
  requiresC2?: boolean;
  shortLabel: string;
  to: string;
}

export interface SectionTab {
  enabled: boolean;
  icon: LucideIcon;
  id: string;
  label: string;
  requiresC2?: boolean;
  to: string;
}

export interface SectionDefinition {
  description: string;
  icon: LucideIcon;
  label: string;
  requiresC2?: boolean;
  requiresProject?: boolean;
  shortLabel: string;
  tabs: SectionTab[];
  to: string;
}

function tab(id: string, label: string, to: string, icon: LucideIcon, requiresC2 = false): SectionTab {
  return { enabled: true, icon, id, label, requiresC2, to };
}

export const sectionDefinitions: Record<ShellSection, SectionDefinition> = {
  assets: {
    description: 'Discovered hosts, services, vulnerabilities, domains, and relationships',
    icon: Layers3,
    label: 'Assets',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Assets',
    tabs: [
      tab('inventory', 'Inventory', '/assets', Layers3, true),
      tab('hosts', 'Hosts', '/assets/hosts', Boxes, true),
      tab('services', 'Services', '/assets/services', ListChecks, true),
      tab('vulnerabilities', 'Vulnerabilities', '/assets/vulnerabilities', ShieldCheck, true),
      tab('domains', 'Domains', '/assets/domains', Crosshair, true),
      tab('cloud-resources', 'Cloud Resources', '/assets/cloud-resources', Boxes, true),
      tab('relationships', 'Relationships', '/assets/relationships', Activity, true),
      tab('modules', 'Modules', '/modules', ListChecks, true),
    ],
    to: '/assets',
  },
  beacons: {
    description: 'Controlled systems reporting through the active C2 backend',
    icon: RadioTower,
    label: 'Beacons',
    requiresC2: true,
    shortLabel: 'Beacons',
    tabs: [
      tab('overview', 'Overview', '/beacons', RadioTower, true),
      tab('sessions', 'Sessions', '/beacons/sessions', TerminalSquare, true),
      tab('groups', 'Groups', '/beacons/groups', Layers3, true),
      tab('profiles', 'Profiles', '/beacons/profiles', Settings, true),
      tab('deploy', 'Deploy', '/beacons/deploy', Cable, true),
    ],
    to: '/beacons',
  },
  exploits: {
    description: 'Exploit catalog, suggestions, execution planning, and results',
    icon: ShieldCheck,
    label: 'Exploits',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Exploits',
    tabs: [
      tab('browser', 'Browser', '/exploits', ShieldCheck, true),
      tab('suggestions', 'Suggestions', '/exploits/suggestions', Activity, true),
      tab('execution', 'Execution', '/exploits/execution', TerminalSquare, true),
      tab('results', 'Results', '/exploits/results', ListChecks, true),
    ],
    to: '/exploits',
  },
  health: {
    description: 'Authenticated readiness',
    icon: HeartPulse,
    label: 'System health',
    shortLabel: 'Health',
    tabs: [
      tab('readiness', 'Readiness', '/health', HeartPulse),
      tab('liveness', 'Liveness', '/health/live', Activity),
    ],
    to: '/health',
  },
  home: {
    description: 'Local BFF and C2 backend overview',
    icon: Home,
    label: 'Home',
    shortLabel: 'Home',
    tabs: [
      tab('overview', 'Overview', '/home', Home),
      tab('activity-feed', 'Activity Feed', '/home/activity', Activity),
      tab('quick-actions', 'Quick Actions', '/home/actions', ListChecks),
    ],
    to: '/home',
  },
  loot: {
    description: 'Credentials, files, secrets, quick-save, and artifact search',
    icon: KeyRound,
    label: 'Loot',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Loot',
    tabs: [
      tab('credentials', 'Credentials', '/loot', KeyRound, true),
      tab('files', 'Files', '/loot/files', FileArchive, true),
      tab('secrets', 'Secrets', '/loot/secrets', ShieldCheck, true),
      tab('quick-save', 'Quick Save', '/loot/quick-save', Boxes, true),
      tab('search', 'Search', '/loot/search', Crosshair, true),
    ],
    to: '/loot',
  },
  payloads: {
    description: 'Payload generation, encryption, obfuscation, and output staging',
    icon: Boxes,
    label: 'Payloads',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Payloads',
    tabs: [
      tab('generator', 'Generator', '/payloads', Boxes, true),
      tab('encrypter', 'Encrypter', '/payloads/encrypter', ShieldCheck, true),
      tab('obfuscator', 'Obfuscator', '/payloads/obfuscator', TerminalSquare, true),
      tab('traffic-shaping', 'Traffic Shaping', '/payloads/traffic-shaping', Cable, true),
      tab('output', 'Output', '/payloads/output', FileArchive, true),
    ],
    to: '/payloads',
  },
  projects: {
    description: 'Scoped target management',
    icon: FolderKanban,
    label: 'Projects',
    requiresC2: true,
    shortLabel: 'Projects',
    tabs: [
      tab('projects', 'Projects', '/projects', FolderKanban, true),
      tab('scope', 'Scope', '/projects/scope', ShieldCheck, true),
      tab('timeline', 'Timeline', '/projects/timeline', Activity, true),
      tab('team', 'Team', '/projects/team', Settings, true),
    ],
    to: '/projects',
  },
  recon: {
    description: 'Discovery tool orchestration',
    icon: Crosshair,
    label: 'Recon',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Recon',
    tabs: [
      tab('tools', 'Tools', '/recon', Crosshair, true),
      tab('runs', 'Runs', '/recon/runs', ListChecks, true),
      tab('results', 'Results', '/recon/results', Boxes, true),
      tab('activity', 'Activity', '/recon/activity', Activity, true),
    ],
    to: '/recon',
  },
  reports: {
    description: 'Notes, campaign reports, host reports, vulnerability reports, and exports',
    icon: ListChecks,
    label: 'Reports',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Reports',
    tabs: [
      tab('notes', 'Notes', '/reports', ListChecks, true),
      tab('campaign-reports', 'Campaign Reports', '/reports/campaign', FileArchive, true),
      tab('host-reports', 'Host Reports', '/reports/hosts', Boxes, true),
      tab('vulnerability-reports', 'Vulnerability Reports', '/reports/vulnerabilities', ShieldCheck, true),
      tab('exports', 'Exports', '/reports/exports', FileArchive, true),
    ],
    to: '/reports',
  },
  settings: {
    description: 'Workspace preferences',
    icon: Settings,
    label: 'Settings',
    shortLabel: 'Settings',
    tabs: [
      tab('connection', 'Connection', '/settings', Settings),
      tab('infrastructure', 'Infrastructure', '/settings/infrastructure', RadioTower, true),
      tab('profiles', 'Profiles', '/settings/profiles', Cable),
      tab('api-keys', 'API Keys', '/settings/api-keys', KeyRound),
      tab('access', 'Access', '/settings/access', ShieldCheck),
      tab('bff', 'BFF', '/settings/bff', Layers3),
      tab('plugins', 'Plugins', '/settings/plugins', Boxes),
      tab('notifications', 'Notifications', '/settings/notifications', Activity),
    ],
    to: '/settings',
  },
};

export const primaryNav: NavItem[] = [
  sectionDefinitions.home,
  sectionDefinitions.projects,
  sectionDefinitions.recon,
  sectionDefinitions.beacons,
  sectionDefinitions.exploits,
  sectionDefinitions.payloads,
  sectionDefinitions.assets,
  sectionDefinitions.reports,
  sectionDefinitions.loot,
  sectionDefinitions.settings,
].map((section) => ({
  enabled: true,
  icon: section.icon,
  label: section.label,
  requiresC2: section.requiresC2,
  shortLabel: section.shortLabel,
  to: section.to,
}));

export const healthNav: NavItem = {
  enabled: true,
  icon: sectionDefinitions.health.icon,
  label: sectionDefinitions.health.label,
  shortLabel: sectionDefinitions.health.shortLabel,
  to: sectionDefinitions.health.to,
};

export function getSectionDefinition(section: ShellSection): SectionDefinition {
  return sectionDefinitions[section];
}

export function getSectionTab(section: ShellSection, tabId?: string): SectionTab {
  const definition = getSectionDefinition(section);
  return definition.tabs.find((tabItem) => tabItem.id === tabId) ?? definition.tabs[0];
}

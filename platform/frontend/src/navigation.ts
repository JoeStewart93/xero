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
  | 'modules'
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
  /** When true, section uses in-content side nav instead of top sub-nav. */
  usesSideNav?: boolean;
}

function tab(
  id: string,
  label: string,
  to: string,
  icon: LucideIcon,
  requiresC2 = false,
  enabled = true,
): SectionTab {
  return { enabled, icon, id, label, requiresC2, to };
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
      tab('hosts', 'Hosts', '/assets/hosts', Boxes, true, false),
      tab('services', 'Services', '/assets/services', ListChecks, true, false),
      tab('vulnerabilities', 'Vulnerabilities', '/assets/vulnerabilities', ShieldCheck, true, false),
      tab('domains', 'Domains', '/assets/domains', Crosshair, true, false),
      tab('cloud-resources', 'Cloud Resources', '/assets/cloud-resources', Boxes, true, false),
      tab('relationships', 'Relationships', '/assets/relationships', Activity, true, false),
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
      tab('roster', 'Roster', '/beacons', RadioTower, true),
      tab('sessions', 'Sessions', '/beacons/sessions', TerminalSquare, true),
      tab('groups', 'Groups', '/beacons/groups', Layers3, true, false),
      tab('profiles', 'Profiles', '/beacons/profiles', Settings, true, false),
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
      tab('browser', 'Browser', '/exploits', ShieldCheck, true, false),
      tab('suggestions', 'Suggestions', '/exploits/suggestions', Activity, true, false),
      tab('execution', 'Execution', '/exploits/execution', TerminalSquare, true, false),
      tab('results', 'Results', '/exploits/results', ListChecks, true, false),
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
      tab('liveness', 'Liveness', '/health/live', Activity, false, false),
    ],
    to: '/health',
  },
  home: {
    description: 'Local BFF and C2 backend overview',
    icon: Home,
    label: 'Home',
    shortLabel: 'Home',
    tabs: [tab('overview', 'Overview', '/home', Home)],
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
      tab('credentials', 'Credentials', '/loot', KeyRound, true, false),
      tab('files', 'Files', '/loot/files', FileArchive, true, false),
      tab('secrets', 'Secrets', '/loot/secrets', ShieldCheck, true, false),
      tab('quick-save', 'Quick Save', '/loot/quick-save', Boxes, true, false),
      tab('search', 'Search', '/loot/search', Crosshair, true, false),
    ],
    to: '/loot',
  },
  modules: {
    description: 'Module catalog and launch paths',
    icon: ListChecks,
    label: 'Modules',
    requiresC2: true,
    shortLabel: 'Modules',
    tabs: [tab('catalog', 'Catalog', '/modules', ListChecks, true)],
    to: '/modules',
  },
  payloads: {
    description: 'Payload generation, encryption, obfuscation, and output staging',
    icon: Boxes,
    label: 'Payloads',
    requiresC2: true,
    requiresProject: true,
    shortLabel: 'Payloads',
    tabs: [
      tab('generator', 'Generator', '/payloads', Boxes, true, false),
      tab('encrypter', 'Encrypter', '/payloads/encrypter', ShieldCheck, true, false),
      tab('obfuscator', 'Obfuscator', '/payloads/obfuscator', TerminalSquare, true, false),
      tab('traffic-patterns', 'Traffic Patterns', '/payloads/traffic-patterns', Cable, true),
      tab('output', 'Output', '/payloads/output', FileArchive, true, false),
    ],
    to: '/payloads/traffic-patterns',
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
      tab('timeline', 'Timeline', '/projects/timeline', Activity, true, false),
      tab('team', 'Team', '/projects/team', Settings, true, false),
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
    tabs: [tab('launch', 'Launch', '/recon', Crosshair, true)],
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
      tab('notes', 'Notes', '/reports', ListChecks, true, false),
      tab('campaign-reports', 'Campaign Reports', '/reports/campaign', FileArchive, true, false),
      tab('host-reports', 'Host Reports', '/reports/hosts', Boxes, true, false),
      tab('vulnerability-reports', 'Vulnerability Reports', '/reports/vulnerabilities', ShieldCheck, true, false),
      tab('exports', 'Exports', '/reports/exports', FileArchive, true, false),
    ],
    to: '/reports',
  },
  settings: {
    description: 'Workspace preferences',
    icon: Settings,
    label: 'Settings',
    shortLabel: 'Settings',
    tabs: [],
    to: '/settings',
    usesSideNav: true,
  },
};

export const settingsSideNav: SectionTab[] = [
  tab('connection', 'Connection', '/settings', Settings),
  tab('infrastructure', 'Infrastructure', '/settings/infrastructure', RadioTower, true),
  tab('grouping', 'Grouping', '/settings/grouping', Layers3, true),
  tab('api-keys', 'API Keys', '/settings/api-keys', KeyRound, false, false),
];

export const primaryNav: NavItem[] = [
  sectionDefinitions.home,
  sectionDefinitions.projects,
  sectionDefinitions.recon,
  sectionDefinitions.beacons,
  sectionDefinitions.exploits,
  sectionDefinitions.payloads,
  sectionDefinitions.modules,
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

export function getVisibleTabs(section: ShellSection): SectionTab[] {
  return getSectionDefinition(section).tabs.filter((item) => item.enabled);
}

export function getSectionTab(section: ShellSection, tabId?: string): SectionTab {
  const definition = getSectionDefinition(section);
  return definition.tabs.find((tabItem) => tabItem.id === tabId) ?? definition.tabs[0];
}

/** Routes that must exist in App.tsx for every enabled tab. */
export function enabledTabRoutes(): Array<{ section: ShellSection; tab: SectionTab }> {
  return (Object.keys(sectionDefinitions) as ShellSection[]).flatMap((section) =>
    getVisibleTabs(section).map((tabItem) => ({ section, tab: tabItem })),
  );
}

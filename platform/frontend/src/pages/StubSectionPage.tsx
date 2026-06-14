import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { getSectionDefinition, getSectionTab, ShellSection } from '../navigation';
import { useC2Connection } from '../useC2Connection';

interface StubSectionPageProps {
  section: ShellSection;
  tabId?: string;
}

export function StubSectionPage({ section, tabId }: StubSectionPageProps) {
  const definition = getSectionDefinition(section);
  const activeTab = getSectionTab(section, tabId);
  const { connection } = useC2Connection();
  const needsC2 = definition.requiresC2 || activeTab.requiresC2;

  return (
    <AppShell description={definition.description} section={section} title={definition.label} wide>
      {needsC2 && !connection ? (
        <C2RequiredPanel />
      ) : (
        <section className="workspace-panel workspace-panel--flat planned-section-empty" aria-label={`${activeTab.label} planned`}>
          <h2>{activeTab.label}</h2>
          <p className="muted-text">{definition.description}</p>
          <p className="planned-section-note">This surface is planned. No operations can be dispatched yet.</p>
        </section>
      )}
    </AppShell>
  );
}

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { getSectionDefinition, ShellSection } from '../navigation';
import { useC2Connection } from '../useC2Connection';

interface PlannedSectionPageProps {
  section: ShellSection;
}

export function PlannedSectionPage({ section }: PlannedSectionPageProps) {
  const definition = getSectionDefinition(section);
  const { connection } = useC2Connection();
  const needsC2 = definition.requiresC2;

  return (
    <AppShell description={definition.description} section={section} title={definition.label} wide>
      {needsC2 && !connection ? (
        <C2RequiredPanel />
      ) : (
        <section className="workspace-panel workspace-panel--flat planned-section-empty" aria-label={`${definition.label} planned`}>
          <h2>{definition.label}</h2>
          <p className="muted-text">{definition.description}</p>
          <p className="planned-section-note">This section is planned. No operations can be dispatched from this surface yet.</p>
        </section>
      )}
    </AppShell>
  );
}

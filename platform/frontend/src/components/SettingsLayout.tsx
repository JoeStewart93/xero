import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

import { settingsSideNav } from '../navigation';

interface SettingsLayoutProps {
  children: ReactNode;
}

function activeClass(baseClass: string, isActive: boolean) {
  return isActive ? `${baseClass} is-active` : baseClass;
}

export function SettingsLayout({ children }: SettingsLayoutProps) {
  const visibleItems = settingsSideNav.filter((item) => item.enabled);

  return (
    <div className="settings-layout">
      <nav aria-label="Settings sections" className="settings-side-nav">
        {visibleItems.map((item) => (
          <NavLink
            className={({ isActive }) => activeClass('settings-side-nav-link', isActive)}
            end={item.to === '/settings'}
            key={item.id}
            to={item.to}
          >
            {item.label}
          </NavLink>
        ))}
        {settingsSideNav
          .filter((item) => !item.enabled)
          .map((item) => (
            <span aria-disabled="true" className="settings-side-nav-link settings-side-nav-link--disabled" key={item.id} title="Planned">
              {item.label}
            </span>
          ))}
      </nav>
      <div className="settings-layout-content">{children}</div>
    </div>
  );
}

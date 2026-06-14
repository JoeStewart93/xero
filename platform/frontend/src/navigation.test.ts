import { describe, expect, it } from 'vitest';

import { enabledTabRoutes, getVisibleTabs, sectionDefinitions } from './navigation';

describe('navigation', () => {
  it('exposes only enabled tabs in getVisibleTabs', () => {
    expect(getVisibleTabs('home').map((tab) => tab.id)).toEqual(['overview']);
    expect(getVisibleTabs('beacons').map((tab) => tab.id)).toEqual(['roster', 'sessions', 'deploy']);
    expect(getVisibleTabs('settings')).toEqual([]);
  });

  it('includes modules as a primary section', () => {
    expect(sectionDefinitions.modules.to).toBe('/modules');
    expect(getVisibleTabs('modules').map((tab) => tab.id)).toEqual(['catalog']);
  });

  it('lists enabled tab routes with valid paths', () => {
    const routes = enabledTabRoutes();
    expect(routes.length).toBeGreaterThan(0);
    for (const { tab } of routes) {
      expect(tab.to.startsWith('/')).toBe(true);
      expect(tab.enabled).toBe(true);
    }
  });
});

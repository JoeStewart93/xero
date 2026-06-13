import { useCallback, useEffect, useMemo, useState } from 'react';

import { getModules } from '../api';
import type { ModuleDefinition } from '../api';
import type { C2Connection } from '../c2ConnectionContext';
import { filterModules, moduleCategories } from '../modules/moduleCatalog';
import type { ModuleFilters } from '../modules/moduleCatalog';

export function useModuleCatalog(connection: C2Connection | null, filters: ModuleFilters) {
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [modules, setModules] = useState<ModuleDefinition[]>([]);

  const loadModules = useCallback(async () => {
    if (!connection) {
      setModules([]);
      return;
    }
    setIsLoading(true);
    try {
      const response = await getModules(connection.baseUrl, connection.accessToken);
      setModules(response.items);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load module inventory.');
    } finally {
      setIsLoading(false);
    }
  }, [connection]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadModules(), 0);
    return () => window.clearTimeout(handle);
  }, [loadModules]);

  const categories = useMemo(() => moduleCategories(modules), [modules]);
  const filteredModules = useMemo(() => filterModules(modules, filters), [filters, modules]);

  return {
    categories,
    error,
    filteredModules,
    isLoading,
    loadModules,
    modules,
  };
}

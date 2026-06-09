import { useContext } from 'react';

import { C2ConnectionContext, C2ConnectionContextValue } from './c2ConnectionContext';

export function useC2Connection(): C2ConnectionContextValue {
  const value = useContext(C2ConnectionContext);
  if (!value) {
    throw new Error('useC2Connection must be used within C2ConnectionProvider');
  }
  return value;
}

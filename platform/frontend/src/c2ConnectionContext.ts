import { createContext } from 'react';

export interface C2Connection {
  accessToken: string;
  baseUrl: string;
  connectedAt: string;
  expiresAt: string;
  service?: string;
  serviceRole?: string;
  status?: string;
  tokenType: 'bearer';
}

export interface C2ConnectionContextValue {
  checkConnection: (baseUrl: string, password: string) => Promise<void>;
  connection: C2Connection | null;
  disconnect: () => void;
  error: string;
  isChecking: boolean;
}

export const C2ConnectionContext = createContext<C2ConnectionContextValue | null>(null);

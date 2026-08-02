import { createContext } from 'react';
import type { User } from '../types/api';

export interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

// Deliberately separate from AuthContext.tsx: a module that exports a component
// alongside anything else defeats react-refresh, which can only hot-swap a file
// whose every export is a component.
export const AuthContext = createContext<AuthContextType | undefined>(undefined);

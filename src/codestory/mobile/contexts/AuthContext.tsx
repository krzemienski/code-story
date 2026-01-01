import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api } from '@/lib/api';
import { saveToken, getToken, removeToken, saveUser, getUser, clearAuth } from '@/lib/storage';

interface User {
  id: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const token = await getToken();
      if (token) {
        const savedUser = await getUser();
        if (savedUser) {
          setUser(savedUser);
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    } finally {
      setIsLoading(false);
    }
  }

  async function login(email: string, password: string) {
    const response = await api.post('/auth/login', { email, password });
    const { access_token, user: userData } = response.data;
    await saveToken(access_token);
    await saveUser(userData);
    setUser(userData);
  }

  async function register(email: string, password: string) {
    const response = await api.post('/auth/register', { email, password });
    const { access_token, user: userData } = response.data;
    await saveToken(access_token);
    await saveUser(userData);
    setUser(userData);
  }

  async function logout() {
    await clearAuth();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

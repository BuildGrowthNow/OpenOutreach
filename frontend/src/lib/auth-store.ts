/**
 * Multi-tenant auth store using Zustand
 * Supports both local JWT and Supabase authentication
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at?: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  loading: boolean;

  // Actions
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  getHeaders: () => Record<string, string>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      loading: false,

      setToken: (token: string) => {
        set({ token });
        localStorage.setItem('token', token);
      },

      setUser: (user: User) => {
        set({ user });
      },

      login: async (email: string, password: string) => {
        set({ loading: true });
        try {
          const response = await fetch('/api/auth/login/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
          }

          const data = await response.json();
          const token = data.access_token;

          set({ token });
          localStorage.setItem('token', token);

          // Fetch user info
          await get().fetchUser();
        } catch (error) {
          console.error('Login failed:', error);
          throw error;
        } finally {
          set({ loading: false });
        }
      },

      register: async (email: string, password: string, fullName: string) => {
        set({ loading: true });
        try {
          const response = await fetch('/api/auth/register/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email,
              password,
              full_name: fullName
            }),
          });

          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
          }

          // Auto-login after registration
          await get().login(email, password);
        } catch (error) {
          console.error('Registration failed:', error);
          throw error;
        } finally {
          set({ loading: false });
        }
      },

      logout: () => {
        set({ token: null, user: null });
        localStorage.removeItem('token');
        localStorage.removeItem('selected_profile_id');
        window.location.href = '/login-v2';
      },

      fetchUser: async () => {
        const token = get().token;
        if (!token) {
          return;
        }

        try {
          const response = await fetch('/api/auth/me/', {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (!response.ok) {
            if (response.status === 401) {
              // Token expired or invalid
              get().logout();
              return;
            }
            throw new Error('Failed to fetch user');
          }

          const user = await response.json();
          set({ user });
        } catch (error) {
          console.error('Failed to fetch user:', error);
        }
      },

      getHeaders: (): Record<string, string> => {
        const token = get().token;
        return token ? { 'Authorization': `Bearer ${token}` } : {};
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
    }
  )
);

// Initialize user on app load
if (typeof window !== 'undefined') {
  const store = useAuthStore.getState();
  if (store.token && !store.user) {
    store.fetchUser();
  }
}

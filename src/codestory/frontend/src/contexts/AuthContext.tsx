/**
 * Authentication context provider for React.
 *
 * Provides auth state and methods throughout the application
 * using Supabase Auth.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import type { User, Session } from '@supabase/supabase-js'
import {
  supabase,
  signInWithPassword,
  signUp as supabaseSignUp,
  signOut as supabaseSignOut,
  signInWithOAuth,
  resetPassword as supabaseResetPassword,
  getProfile,
  type Profile,
} from '@/lib/supabase'

// =============================================================================
// Types
// =============================================================================

interface AuthState {
  user: User | null
  profile: Profile | null
  session: Session | null
  isLoading: boolean
  isAuthenticated: boolean
}

interface AuthContextValue extends AuthState {
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, name?: string) => Promise<void>
  signOut: () => Promise<void>
  signInWithGitHub: () => Promise<void>
  signInWithGoogle: () => Promise<void>
  resetPassword: (email: string) => Promise<void>
  refreshProfile: () => Promise<void>
}

// =============================================================================
// Context
// =============================================================================

const AuthContext = createContext<AuthContextValue | null>(null)

// =============================================================================
// Provider
// =============================================================================

interface AuthProviderProps {
  children: React.ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    profile: null,
    session: null,
    isLoading: true,
    isAuthenticated: false,
  })

  // Load profile when user changes
  const loadProfile = useCallback(async (userId: string) => {
    try {
      const profile = await getProfile(userId)
      setState((prev) => ({ ...prev, profile }))
    } catch (error) {
      console.error('Failed to load profile:', error)
    }
  }, [])

  // Initialize auth state
  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setState((prev) => ({
        ...prev,
        session,
        user: session?.user ?? null,
        isAuthenticated: !!session?.user,
        isLoading: false,
      }))

      if (session?.user) {
        loadProfile(session.user.id)
      }
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('Auth state change:', event)

      setState((prev) => ({
        ...prev,
        session,
        user: session?.user ?? null,
        isAuthenticated: !!session?.user,
        isLoading: false,
        // Clear profile on sign out
        profile: event === 'SIGNED_OUT' ? null : prev.profile,
      }))

      // Load profile on sign in
      if (event === 'SIGNED_IN' && session?.user) {
        loadProfile(session.user.id)
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [loadProfile])

  // =============================================================================
  // Auth Methods
  // =============================================================================

  const signIn = useCallback(async (email: string, password: string) => {
    setState((prev) => ({ ...prev, isLoading: true }))
    try {
      await signInWithPassword(email, password)
    } finally {
      setState((prev) => ({ ...prev, isLoading: false }))
    }
  }, [])

  const signUp = useCallback(async (email: string, password: string, name?: string) => {
    setState((prev) => ({ ...prev, isLoading: true }))
    try {
      await supabaseSignUp(email, password, name)
    } finally {
      setState((prev) => ({ ...prev, isLoading: false }))
    }
  }, [])

  const signOut = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true }))
    try {
      await supabaseSignOut()
    } finally {
      setState((prev) => ({ ...prev, isLoading: false }))
    }
  }, [])

  const signInWithGitHub = useCallback(async () => {
    await signInWithOAuth('github')
  }, [])

  const signInWithGoogle = useCallback(async () => {
    await signInWithOAuth('google')
  }, [])

  const resetPassword = useCallback(async (email: string) => {
    await supabaseResetPassword(email)
  }, [])

  const refreshProfile = useCallback(async () => {
    if (state.user) {
      await loadProfile(state.user.id)
    }
  }, [state.user, loadProfile])

  // =============================================================================
  // Context Value
  // =============================================================================

  const value: AuthContextValue = {
    ...state,
    signIn,
    signUp,
    signOut,
    signInWithGitHub,
    signInWithGoogle,
    resetPassword,
    refreshProfile,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook to access auth state and methods.
 * Must be used within an AuthProvider.
 */
export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}

/**
 * Hook to require authentication.
 * Returns the user or throws if not authenticated.
 */
export function useRequireAuth() {
  const { user, isAuthenticated, isLoading } = useAuth()

  if (!isLoading && !isAuthenticated) {
    throw new Error('Authentication required')
  }

  return { user, isLoading }
}

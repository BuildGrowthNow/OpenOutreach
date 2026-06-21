/**
 * Supabase Exports
 * 
 * Centralized exports for Supabase-related functionality.
 */

// Client configuration
export { supabase, isSignedIn, getCurrentUser, signOutUser } from './client'

// Utility functions
export type { Session, User } from '@supabase/supabase-js'
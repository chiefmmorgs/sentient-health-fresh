import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

export interface Profile {
  name: string
  description: string
  planner_mappings: Record<string, string>
  executor_mappings: Record<string, string>
  atomizer: string
  aggregator: string
  plan_modifier: string
  default_planner: string
  default_executor: string
  is_current: boolean
  is_valid: boolean
  validation?: {
    blueprint_valid: boolean
    missing_agents?: string[]
  }
}

interface ProfileState {
  profiles: Profile[]
  currentProfile: string | null
  isLoading: boolean
  error: string | null
  
  // Actions
  setProfiles: (profiles: Profile[]) => void
  setCurrentProfile: (profileName: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  switchProfile: (profileName: string) => Promise<void>
  loadProfiles: () => Promise<void>
}

export const useProfileStore = create<ProfileState>()(
  devtools(
    (set, get) => ({
      profiles: [],
      currentProfile: null,
      isLoading: false,
      error: null,

      setProfiles: (profiles) => set({ profiles }),
      setCurrentProfile: (profileName) => set({ currentProfile: profileName }),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),

      switchProfile: async (profileName: string) => {
        const { setLoading, setError, setCurrentProfile } = get()
        
        try {
          setLoading(true)
          setError(null)

          const response = await fetch(`/api/profiles/${profileName}/switch`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
          })

          const result = await response.json()

          if (result.success) {
            setCurrentProfile(profileName)
            // Update the profiles list to reflect the change
            set((state) => ({
              profiles: state.profiles.map(p => ({
                ...p,
                is_current: p.name === profileName
              }))
            }))
          } else {
            setError(result.error || 'Failed to switch profile')
          }
        } catch (error) {
          console.error('Failed to switch profile:', error)
          setError(error instanceof Error ? error.message : 'Failed to switch profile')
        } finally {
          setLoading(false)
        }
      },

      loadProfiles: async () => {
        const { setLoading, setError, setProfiles, setCurrentProfile } = get()
        
        try {
          setLoading(true)
          setError(null)

          const response = await fetch('/api/profiles')
          const data = await response.json()

          if (response.ok) {
            setProfiles(data.profiles)
            setCurrentProfile(data.current_profile)
          } else {
            setError(data.error || 'Failed to load profiles')
          }
        } catch (error) {
          console.error('Failed to load profiles:', error)
          setError(error instanceof Error ? error.message : 'Failed to load profiles')
        } finally {
          setLoading(false)
        }
      },
    }),
    {
      name: 'profile-store',
    }
  )
) 
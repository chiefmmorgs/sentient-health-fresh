import React, { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { 
  Bot, 
  CheckCircle, 
  AlertCircle, 
  Loader2,
  Info
} from 'lucide-react'
import { useProfileStore } from '@/stores/profileStore'
import { cn } from '@/lib/utils'

const ProfileSelector: React.FC = () => {
  const {
    profiles,
    currentProfile,
    isLoading,
    error,
    switchProfile,
    loadProfiles
  } = useProfileStore()

  const [isOpen, setIsOpen] = useState(false)

  // Load profiles on mount
  useEffect(() => {
    loadProfiles()
  }, [loadProfiles])

  const currentProfileData = profiles.find(p => p.is_current)

  const handleProfileChange = async (profileName: string) => {
    if (profileName === currentProfile) return
    
    await switchProfile(profileName)
    setIsOpen(false)
  }

  const getProfileIcon = (profile: any) => {
    if (profile.is_valid) {
      return <CheckCircle className="w-4 h-4 text-green-500" />
    } else {
      return <AlertCircle className="w-4 h-4 text-yellow-500" />
    }
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn(
            "text-xs min-w-[140px] justify-start",
            error && "border-red-500"
          )}
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Loading...
            </>
          ) : (
            <>
              <Bot className="w-4 h-4 mr-2" />
              {currentProfile || 'Select Profile'}
            </>
          )}
        </Button>
      </PopoverTrigger>
      
      <PopoverContent className="w-80 p-0" align="end">
        <div className="p-4">
          <div className="flex items-center space-x-2 mb-3">
            <Bot className="w-5 h-5" />
            <h4 className="font-medium">Agent Profiles</h4>
          </div>
          
          {error && (
            <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          {/* Current Profile Info */}
          {currentProfileData && (
            <div className="mb-4 p-3 bg-muted/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">Current Profile</span>
                <Badge variant="default" className="text-xs">
                  Active
                </Badge>
              </div>
              <div className="text-sm text-muted-foreground">
                {currentProfileData.description}
              </div>
            </div>
          )}

          <Separator className="mb-3" />

          {/* Profile List */}
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {profiles.map((profile) => (
              <div
                key={profile.name}
                className={cn(
                  "flex items-center justify-between p-2 rounded-lg cursor-pointer hover:bg-muted/50 transition-colors",
                  profile.is_current && "bg-muted"
                )}
                onClick={() => handleProfileChange(profile.name)}
              >
                <div className="flex items-center space-x-3 flex-1">
                  {getProfileIcon(profile)}
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {profile.name}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {profile.description}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {profile.is_current && (
                    <Badge variant="default" className="text-xs">
                      Current
                    </Badge>
                  )}
                  {!profile.is_valid && (
                    <Badge variant="outline" className="text-xs">
                      Issues
                    </Badge>
                  )}
                </div>
              </div>
            ))}
          </div>

          {profiles.length === 0 && !isLoading && (
            <div className="text-center py-4 text-sm text-muted-foreground">
              No profiles available
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export default ProfileSelector
import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { CheckCircle, AlertCircle, Bot, Cog, Play } from 'lucide-react'
import { Profile } from '@/stores/profileStore'

interface ProfileDetailsProps {
  profile: Profile
}

const ProfileDetails: React.FC<ProfileDetailsProps> = ({ profile }) => {
  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center space-x-2">
            <Bot className="w-5 h-5" />
            <span>{profile.name}</span>
          </CardTitle>
          <div className="flex items-center space-x-2">
            {profile.is_current && (
              <Badge variant="default" className="text-xs">
                Active
              </Badge>
            )}
            {profile.is_valid ? (
              <CheckCircle className="w-4 h-4 text-green-500" />
            ) : (
              <AlertCircle className="w-4 h-4 text-yellow-500" />
            )}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {profile.description}
        </p>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Planner Mappings */}
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <Cog className="w-4 h-4" />
            <h4 className="font-medium text-sm">Task Planners</h4>
          </div>
          <div className="space-y-1">
            {Object.entries(profile.planner_mappings).map(([taskType, planner]) => (
              <div key={taskType} className="flex items-center justify-between text-xs">
                <Badge variant="outline" className="text-xs">
                  {taskType}
                </Badge>
                <span className="text-muted-foreground">{planner}</span>
              </div>
            ))}
          </div>
        </div>

        <Separator />

        {/* Executor Mappings */}
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <Play className="w-4 h-4" />
            <h4 className="font-medium text-sm">Task Executors</h4>
          </div>
          <div className="space-y-1">
            {Object.entries(profile.executor_mappings).map(([taskType, executor]) => (
              <div key={taskType} className="flex items-center justify-between text-xs">
                <Badge variant="outline" className="text-xs">
                  {taskType}
                </Badge>
                <span className="text-muted-foreground">{executor}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Validation Issues */}
        {!profile.is_valid && profile.validation?.missing_agents && (
          <>
            <Separator />
            <div>
              <h4 className="font-medium text-sm text-yellow-600 dark:text-yellow-400 mb-2">
                Validation Issues
              </h4>
              <div className="space-y-1">
                {profile.validation.missing_agents.map((agent, index) => (
                  <div key={index} className="text-xs text-muted-foreground">
                    • Missing agent: {agent}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default ProfileDetails 
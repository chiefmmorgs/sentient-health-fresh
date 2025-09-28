import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Info, Settings, Zap, Database, MessageSquare, Layers, Clock, Target, Loader2 } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import ProjectProfileSelector from '@/components/profile/ProjectProfileSelector'

export interface ProjectConfig {
  // Profile Configuration
  profile?: {
    name: string
    displayName?: string
  }
  
  // LLM Configuration
  llm: {
    provider: string
    model: string
    temperature: number
    max_tokens?: number
    timeout: number
    max_retries: number
  }
  
  // Execution Configuration
  execution: {
    max_concurrent_nodes: number
    max_execution_steps: number
    max_recursion_depth: number
    task_timeout_seconds: number
    enable_hitl: boolean
    hitl_root_plan_only: boolean
    hitl_timeout_seconds: number
    hitl_after_plan_generation: boolean
    hitl_after_modified_plan: boolean
    hitl_after_atomizer: boolean
    hitl_before_execute: boolean
    max_replan_attempts?: number
    execution_timeout?: number
    skip_atomization?: boolean
    force_root_node_planning?: boolean
  }
  
  // Cache Configuration
  cache: {
    enabled: boolean
    ttl_seconds: number
    max_size: number
    cache_type: string
  }
  
  // Project-specific settings
  project: {
    goal: string
    max_steps: number
    description?: string
  }
}

interface ProjectConfigPanelProps {
  config: ProjectConfig
  onChange: (config: ProjectConfig) => void
  onSubmit: () => void
  onCancel: () => void
  isCreating: boolean
}

const ProjectConfigPanel: React.FC<ProjectConfigPanelProps> = ({
  config,
  onChange,
  onSubmit,
  onCancel,
  isCreating
}) => {
  const [activeTab, setActiveTab] = useState('project')

  const updateConfig = (section: keyof ProjectConfig, field: string, value: any) => {
    onChange({
      ...config,
      [section]: {
        ...config[section],
        [field]: value
      }
    })
  }

  const handleProfileChange = (profileName: string) => {
    onChange({
      ...config,
      profile: {
        name: profileName,
        displayName: profileName === 'crypto_analytics_agent' ? 'Crypto Analytics Agent' : 
                     profileName === 'deep_research_agent' ? 'Deep Research Agent' : 'General Agent'
      }
    })
  }

  return (
    <TooltipProvider>
      <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Project Configuration</h2>
        <p className="text-muted-foreground">
          Configure your project settings and execution parameters
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="project">Project</TabsTrigger>
          <TabsTrigger value="profile">Agent Profile</TabsTrigger>
          <TabsTrigger value="execution">Execution</TabsTrigger>
          <TabsTrigger value="cache">Cache</TabsTrigger>
        </TabsList>

        <TabsContent value="project" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Project Details
              </CardTitle>
              <CardDescription>
                Define your project goal and basic parameters
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="goal">Project Goal *</Label>
                <Textarea
                  id="goal"
                  value={config.project.goal || ''}
                  onChange={(e) => updateConfig('project', 'goal', e.target.value)}
                  placeholder="Describe what you want to research or accomplish..."
                  className="min-h-[100px]"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_steps">Maximum Steps</Label>
                  <Input
                    id="max_steps"
                    type="number"
                    value={config.project.max_steps || 250}
                    onChange={(e) => updateConfig('project', 'max_steps', parseInt(e.target.value) || 250)}
                    min={10}
                    max={1000}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum number of execution steps (10-1000)
                  </p>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="description">Description (Optional)</Label>
                  <Input
                    id="description"
                    value={config.project.description || ''}
                    onChange={(e) => updateConfig('project', 'description', e.target.value)}
                    placeholder="Brief project description..."
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="profile" className="space-y-6">
          <ProjectProfileSelector
            selectedProfile={config.profile?.name || 'crypto_analytics_agent'}
            onProfileChange={handleProfileChange}
          />
        </TabsContent>

        <TabsContent value="execution" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                Execution Settings
              </CardTitle>
              <CardDescription>
                Configure how the system executes tasks
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_recursion_depth">Max Recursion Depth</Label>
                  <Input
                    id="max_recursion_depth"
                    type="number"
                    min="1"
                    max="10"
                    value={config.execution?.max_recursion_depth || 2}
                    onChange={(e) => updateConfig('execution', 'max_recursion_depth', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">
                    Maximum depth for task decomposition (1-10)
                  </p>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="max_concurrent_nodes">Max Concurrent Nodes</Label>
                  <Input
                    id="max_concurrent_nodes"
                    type="number"
                    min="1"
                    max="20"
                    value={config.execution?.max_concurrent_nodes || 6}
                    onChange={(e) => updateConfig('execution', 'max_concurrent_nodes', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">
                    Maximum number of nodes to process simultaneously
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_execution_steps">Max Execution Steps</Label>
                  <Input
                    id="max_execution_steps"
                    type="number"
                    min="10"
                    max="1000"
                    value={config.execution?.max_execution_steps || 250}
                    onChange={(e) => updateConfig('execution', 'max_execution_steps', parseInt(e.target.value))}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="task_timeout_seconds">Task Timeout (seconds)</Label>
                  <Input
                    id="task_timeout_seconds"
                    type="number"
                    min="30"
                    max="3600"
                    value={config.execution?.task_timeout_seconds || 300}
                    onChange={(e) => updateConfig('execution', 'task_timeout_seconds', parseInt(e.target.value))}
                  />
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <h4 className="font-medium">Human-in-the-Loop (HITL) Settings</h4>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="enable_hitl">Enable HITL</Label>
                    <p className="text-sm text-muted-foreground">
                      Allow human intervention during execution
                    </p>
                  </div>
                  <Switch
                    id="enable_hitl"
                    checked={config.execution?.enable_hitl || false}
                    onCheckedChange={(checked) => updateConfig('execution', 'enable_hitl', checked)}
                  />
                </div>

                {config.execution?.enable_hitl && (
                  <div className="space-y-4 pl-4 border-l-2 border-muted">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="hitl_root_plan_only">Root Plan Only</Label>
                      <Switch
                        id="hitl_root_plan_only"
                        checked={config.execution?.hitl_root_plan_only || false}
                        onCheckedChange={(checked) => updateConfig('execution', 'hitl_root_plan_only', checked)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="hitl_timeout_seconds">HITL Timeout (seconds)</Label>
                      <Input
                        id="hitl_timeout_seconds"
                        type="number"
                        min="60"
                        max="3600"
                        value={config.execution?.hitl_timeout_seconds || 300}
                        onChange={(e) => updateConfig('execution', 'hitl_timeout_seconds', parseInt(e.target.value))}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="hitl_after_plan_generation">After Plan Generation</Label>
                        <Switch
                          id="hitl_after_plan_generation"
                          checked={config.execution?.hitl_after_plan_generation || false}
                          onCheckedChange={(checked) => updateConfig('execution', 'hitl_after_plan_generation', checked)}
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <Label htmlFor="hitl_after_modified_plan">After Modified Plan</Label>
                        <Switch
                          id="hitl_after_modified_plan"
                          checked={config.execution?.hitl_after_modified_plan || false}
                          onCheckedChange={(checked) => updateConfig('execution', 'hitl_after_modified_plan', checked)}
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <Label htmlFor="hitl_after_atomizer">After Atomizer</Label>
                        <Switch
                          id="hitl_after_atomizer"
                          checked={config.execution?.hitl_after_atomizer || false}
                          onCheckedChange={(checked) => updateConfig('execution', 'hitl_after_atomizer', checked)}
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <Label htmlFor="hitl_before_execute">Before Execute</Label>
                        <Switch
                          id="hitl_before_execute"
                          checked={config.execution?.hitl_before_execute || false}
                          onCheckedChange={(checked) => updateConfig('execution', 'hitl_before_execute', checked)}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <Separator />

              {/* Atomization Controls */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-base font-medium flex items-center gap-2">
                    <Target className="h-4 w-4" />
                    Atomization & Planning
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Control how tasks are decomposed and atomized
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="skip_atomization">Skip Atomization</Label>
                      <p className="text-sm text-muted-foreground">
                        Bypass atomizer and use hierarchy/depth rules
                      </p>
                    </div>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Switch
                          id="skip_atomization"
                          checked={config.execution?.skip_atomization || false}
                          onCheckedChange={(checked) => updateConfig('execution', 'skip_atomization', checked)}
                        />
                      </TooltipTrigger>
                      <TooltipContent>
                        When enabled, tasks use max_recursion_depth rules instead of atomizer decisions
                      </TooltipContent>
                    </Tooltip>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="force_root_node_planning">Force Root Planning</Label>
                      <p className="text-sm text-muted-foreground">
                        Always plan root nodes (skip root atomization)
                      </p>
                    </div>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Switch
                          id="force_root_node_planning"
                          checked={config.execution?.force_root_node_planning || true}
                          onCheckedChange={(checked) => updateConfig('execution', 'force_root_node_planning', checked)}
                        />
                      </TooltipTrigger>
                      <TooltipContent>
                        Ensures complex top-level questions always get decomposed
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cache" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Cache Configuration
              </CardTitle>
              <CardDescription>
                Configure caching behavior for improved performance
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="cache_enabled">Enable Cache</Label>
                  <p className="text-sm text-muted-foreground">
                    Cache results to improve performance
                  </p>
                </div>
                <Switch
                  id="cache_enabled"
                  checked={config.cache.enabled || false}
                  onCheckedChange={(checked) => updateConfig('cache', 'enabled', checked)}
                />
              </div>

              {config.cache.enabled && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="cache_type">Cache Type</Label>
                      <Select
                        value={config.cache.cache_type || 'memory'}
                        onValueChange={(value) => updateConfig('cache', 'cache_type', value)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="file">File</SelectItem>
                          <SelectItem value="memory">Memory</SelectItem>
                          <SelectItem value="redis">Redis</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="cache_ttl">TTL (seconds)</Label>
                      <Input
                        id="cache_ttl"
                        type="number"
                        min="60"
                        max="86400"
                        value={config.cache.ttl_seconds || 3600}
                        onChange={(e) => updateConfig('cache', 'ttl_seconds', parseInt(e.target.value) || 3600)}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="cache_max_size">Max Cache Size</Label>
                    <Input
                      id="cache_max_size"
                      type="number"
                      min="100"
                      max="10000"
                      value={config.cache.max_size || 1000}
                      onChange={(e) => updateConfig('cache', 'max_size', parseInt(e.target.value) || 1000)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Maximum number of items to cache
                    </p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Action Buttons */}
      <div className="flex justify-between mt-8">
        <Button variant="outline" onClick={onCancel} disabled={isCreating}>
          Cancel
        </Button>
        <Button onClick={onSubmit} disabled={isCreating}>
          {isCreating ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Creating Project...
            </>
          ) : (
            'Create Project'
          )}
        </Button>
      </div>
      </div>
    </TooltipProvider>
  )
}

export default ProjectConfigPanel 
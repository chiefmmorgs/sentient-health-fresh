import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Send, Loader2, Settings } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { useProjectStore } from '@/stores/projectStore'
import projectService from '@/services/projectService'
import { toast } from '@/components/ui/use-toast'
import { cn } from '@/lib/utils'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import ProjectConfigPanel, { ProjectConfig } from './ProjectConfigPanel'

const ProjectInput: React.FC = () => {
  const [goal, setGoal] = useState('')
  const [isStarting, setIsStarting] = useState(false)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [isFocused, setIsFocused] = useState(false)
  const { isConnected, setLoading } = useTaskGraphStore()
  const { addProject, getCurrentProject } = useProjectStore()

  // Default configuration
  const [config, setConfig] = useState<ProjectConfig>({
    profile: {
      name: 'crypto_analytics_agent',
      displayName: 'Crypto Analytics Agent'
    },
    llm: {
      provider: 'openai',
      model: 'gpt-4',
      temperature: 0.7,
      timeout: 30,
      max_retries: 3
    },
    execution: {
      max_concurrent_nodes: 6,
      max_execution_steps: 250,
      max_recursion_depth: 2,
      task_timeout_seconds: 300,
      enable_hitl: true,
      hitl_root_plan_only: true,
      hitl_timeout_seconds: 300,
      hitl_after_plan_generation: true,
      hitl_after_modified_plan: true,
      hitl_after_atomizer: false,
      hitl_before_execute: false
    },
    cache: {
      enabled: true,
      ttl_seconds: 3600,
      max_size: 1000,
      cache_type: 'memory'
    },
    project: {
      goal: goal,
      max_steps: 250
    }
  })

  const currentProject = getCurrentProject()

  // Example prompts - shorter for better fit
  const examplePrompts = [
    "Impact of AI on software development",
    "Quantum computing breakthroughs 2024",
    "Renewable energy storage comparison",
    "Remote work effectiveness study",
    "Cryptocurrency market analysis"
  ]

  // Update config when goal changes
  React.useEffect(() => {
    setConfig(prev => ({
      ...prev,
      project: {
        ...prev.project,
        goal: goal
      }
    }))
  }, [goal])

  const handleQuickSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!goal.trim() || !isConnected) return

    console.log('🚀 Starting project with default config')
    await createProject(config)
  }

  const handleConfiguredSubmit = async () => {
    console.log('🚀 Starting project with custom config')
    await createProject(config)
    setShowConfigDialog(false)
  }

  const createProject = async (projectConfig: ProjectConfig) => {
    setIsStarting(true)
    setLoading(true)
    
    try {
      const result = await projectService.createProjectWithConfig(
        projectConfig.project.goal.trim(),
        projectConfig
      )
      addProject(result.project)
      
      toast({
        title: "Project Created",
        description: result.message,
      })
      
      console.log('✅ Project created and started')
    } catch (error) {
      console.error('❌ Failed to create project:', error)
      setLoading(false)
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create project",
        variant: "destructive",
      })
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-6 h-full overflow-y-auto">
      <div className="min-h-full flex flex-col">
        <div className="text-center mb-4">
          <h2 className="text-2xl font-bold mb-2">
            {currentProject ? 'Start Another Project' : 'Start a New Project'}
          </h2>
          <p className="text-muted-foreground text-sm">
            Describe your research goal and watch as the AI breaks it down into manageable tasks
          </p>
        </div>

      <form onSubmit={handleQuickSubmit} className="space-y-4">
        <div className="relative">
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Enter your research goal or question here..."
            className={cn(
              "min-h-[100px] resize-none transition-all",
              !goal && "placeholder:text-muted-foreground/60"
            )}
            disabled={isStarting}
          />
        </div>
        
        {/* Helper text below textarea */}
        {!goal && (
          <div className="text-center -mt-2">
            <p className="text-sm text-muted-foreground italic">
              e.g., "Analyze the impact of AI on software development" or "Research quantum computing breakthroughs in 2024"
            </p>
          </div>
        )}
        
        <div className="flex justify-between items-center">
          <div className="text-sm text-muted-foreground">
            {isConnected ? (
              <span className="text-green-600">✓ Connected to backend</span>
            ) : (
              <span className="text-red-600">✗ Backend disconnected</span>
            )}
          </div>
          
          <div className="flex gap-2">
            {/* Quick Start Button */}
            <Button 
              type="submit" 
              disabled={!goal.trim() || !isConnected || isStarting}
              className="min-w-[120px]"
            >
              {isStarting ? (
                <>
                  <Loader2 className="w-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Quick Start
                </>
              )}
            </Button>

            {/* Configure & Start Button */}
            <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
              <DialogTrigger asChild>
                <Button 
                  type="button"
                  variant="outline"
                  disabled={!goal.trim() || !isConnected || isStarting}
                  className="min-w-[140px]"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Configure & Start
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Configure Project</DialogTitle>
                </DialogHeader>
                <ProjectConfigPanel
                  config={config}
                  onChange={setConfig}
                  onSubmit={handleConfiguredSubmit}
                  onCancel={() => setShowConfigDialog(false)}
                  isCreating={isStarting}
                />
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </form>

        {/* Example Prompts */}
        {!goal && (
          <div className="mt-4 p-3 bg-muted/30 rounded-lg border border-muted">
            <p className="text-sm font-medium mb-2">Need inspiration? Try one of these examples:</p>
            <div className="flex flex-wrap gap-2">
              {examplePrompts.map((prompt, index) => (
                <Button
                  key={index}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="text-xs hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all duration-200"
                  onClick={() => setGoal(prompt)}
                >
                  {prompt}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Configuration Preview */}
        <div className="mt-4 p-3 bg-muted/50 rounded-lg">
          <h4 className="text-sm font-medium mb-2">Current Configuration:</h4>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div>Recursion Depth: {config.execution.max_recursion_depth}</div>
            <div>Cache: {config.cache.cache_type}</div>
            <div>Max Steps: {config.execution.max_execution_steps}</div>
            <div>HITL: {config.execution.enable_hitl ? 
              (config.execution.hitl_root_plan_only ? 'Root Only' : 'Full') : 
              'Disabled'
            }</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProjectInput 
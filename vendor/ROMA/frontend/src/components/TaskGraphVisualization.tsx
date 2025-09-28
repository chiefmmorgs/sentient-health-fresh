import HITLModal from '@/components/hitl/HITLModal'
import { useTaskGraphStore } from '@/stores/taskGraphStore'

const TaskGraphVisualization: React.FC = () => {
  const { currentHITLRequest } = useTaskGraphStore()
  
  return (
    <div className="h-full w-full relative">
      {/* HITL Modal */}
      <HITLModal 
        isOpen={!!currentHITLRequest}
        onClose={() => useTaskGraphStore.getState().setHITLRequest(undefined)}
      />
    </div>
  )
}

export default TaskGraphVisualization 
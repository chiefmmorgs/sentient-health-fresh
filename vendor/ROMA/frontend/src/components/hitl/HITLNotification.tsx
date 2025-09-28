import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { X } from 'lucide-react'

const HITLNotification: React.FC = () => {
  const { currentHITLRequest } = useTaskGraphStore()
  const [isVisible, setIsVisible] = useState(false)
  const [notificationRequest, setNotificationRequest] = useState<any>(null)

  useEffect(() => {
    if (currentHITLRequest && currentHITLRequest !== notificationRequest) {
      // New HITL request - show notification
      setNotificationRequest(currentHITLRequest)
      setIsVisible(true)
      console.log('🤔 HITL Notification: Showing request', currentHITLRequest)
      
      // Auto-hide notification after 5 seconds (but don't clear the actual HITL request)
      const timer = setTimeout(() => {
        setIsVisible(false)
        // Only clear the notification's local state, not the global HITL request
        setTimeout(() => setNotificationRequest(null), 300)
      }, 5000)
      
      return () => clearTimeout(timer)
    }
  }, [currentHITLRequest, notificationRequest])

  // Hide notification if the global HITL request is cleared
  useEffect(() => {
    if (!currentHITLRequest && isVisible) {
      setIsVisible(false)
      setTimeout(() => setNotificationRequest(null), 300)
    }
  }, [currentHITLRequest, isVisible])

  if (!notificationRequest || !isVisible) {
    return null
  }

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-right-full duration-300">
      <Card className="w-80 border-blue-200 bg-blue-50">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="secondary" className="text-xs">
                  🤔 HITL Checkpoint
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {notificationRequest.current_attempt}
                </Badge>
              </div>
              
              <h4 className="font-medium text-sm text-blue-900 mb-1">
                {notificationRequest.checkpoint_name}
              </h4>
              
              <p className="text-xs text-blue-700 mb-2">
                Node: {notificationRequest.node_id}
              </p>
              
              <p className="text-xs text-gray-600 line-clamp-2">
                {notificationRequest.context_message}
              </p>
              
              <div className="mt-2 text-xs text-blue-600">
                💬 Review required - Check the modal for details
              </div>
            </div>
            
            <button
              onClick={() => {
                setIsVisible(false)
                // Only hide the notification, don't clear the global HITL request
                setTimeout(() => setNotificationRequest(null), 300)
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default HITLNotification 
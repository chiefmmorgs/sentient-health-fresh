import React from 'react'
import { EdgeProps, getBezierPath } from 'reactflow'
import { Badge } from '@/components/ui/badge'

const CustomEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  data,
  markerEnd,
}) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const { type, isHighlighted, isDimmed, contentType, sequence } = data || {}
  
  // Enhanced edge styling based on type and state
  const getEnhancedStyle = () => {
    const baseStyle = {
      strokeWidth: isHighlighted ? 3 : 2,
      opacity: isDimmed ? 0.2 : 1,
      transition: 'all 0.3s ease',
      ...style
    }

    switch (type) {
      case 'hierarchy':
        return {
          ...baseStyle,
          stroke: isHighlighted ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))',
          filter: isHighlighted ? 'drop-shadow(0 0 4px hsl(var(--primary)))' : 'none',
        }
      case 'context':
        return {
          ...baseStyle,
          stroke: isHighlighted ? '#10b981' : '#6b7280',
          strokeDasharray: '5,5',
          filter: isHighlighted ? 'drop-shadow(0 0 4px #10b981)' : 'none',
        }
      case 'execution':
        return {
          ...baseStyle,
          stroke: '#f59e0b',
          strokeWidth: 4,
          filter: 'drop-shadow(0 0 6px #f59e0b)',
        }
      default:
        return baseStyle
    }
  }

  const enhancedStyle = getEnhancedStyle()

  return (
    <>
      <path
        id={id}
        style={enhancedStyle}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={markerEnd}
      />
      
      {/* Edge Labels */}
      {(isHighlighted || type === 'execution') && (
        <g>
          {/* Background for label */}
          <rect
            x={labelX - 30}
            y={labelY - 10}
            width={60}
            height={20}
            rx={10}
            fill="white"
            stroke={enhancedStyle.stroke}
            strokeWidth={1}
            opacity={0.9}
          />
          
          {/* Label text */}
          <text
            x={labelX}
            y={labelY + 4}
            textAnchor="middle"
            fontSize={10}
            fontWeight="bold"
            fill={enhancedStyle.stroke}
          >
            {type === 'execution' && sequence ? `#${sequence}` :
             type === 'context' && contentType ? contentType.slice(0, 6) :
             type === 'hierarchy' ? 'child' : 
             type || 'edge'}
          </text>
        </g>
      )}
    </>
  )
}

export default CustomEdge 
import React from 'react'
import { FiTrash2, FiExternalLink } from 'react-icons/fi'

function ResultCard({ item, onDelete }) {
  const sourceClass = `source-badge source-${item.source_type}`

  return (
    <div className="result-card">
      <div className="d-flex justify-content-between align-items-start mb-2">
        <div className="d-flex align-items-center gap-2">
          <span className={sourceClass}>{item.source_type}</span>
          {item.distance !== undefined && (
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              Score: {(1 - item.distance).toFixed(3)}
            </span>
          )}
        </div>
        {onDelete && (
          <button
            className="btn btn-sm"
            style={{ color: '#ef4444' }}
            onClick={() => onDelete(item.id)}
            title="Delete"
          >
            <FiTrash2 />
          </button>
        )}
      </div>

      <p className="mb-2" style={{ lineHeight: 1.6 }}>{item.summary}</p>

      {item.tags && item.tags.length > 0 && (
        <div className="d-flex flex-wrap gap-1 mb-2">
          {item.tags.map((tag, i) => (
            <span key={i} className="badge-tag">{tag}</span>
          ))}
        </div>
      )}

      <div className="d-flex justify-content-between align-items-center" style={{ fontSize: '0.8rem', color: '#64748b' }}>
        <span className="text-truncate" style={{ maxWidth: '70%' }}>{item.source}</span>
        {item.source_type === 'url' || item.source_type === 'bookmark' ? (
          <a
            href={item.source}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#818cf8' }}
          >
            <FiExternalLink />
          </a>
        ) : null}
      </div>
    </div>
  )
}

export default ResultCard

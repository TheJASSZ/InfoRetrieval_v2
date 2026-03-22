import React, { useState, useEffect } from 'react'
import { FiDatabase, FiRefreshCw } from 'react-icons/fi'
import { getStats } from '../services/api'

function Dashboard() {
  const [stats, setStats] = useState(null)

  const fetchStats = async () => {
    try {
      const res = await getStats()
      setStats(res.data)
    } catch {
      setStats(null)
    }
  }

  useEffect(() => { fetchStats() }, [])

  return (
    <div className="d-flex gap-3 flex-wrap">
      <div className="stat-card flex-fill">
        <div className="d-flex align-items-center justify-content-center gap-2 mb-2">
          <FiDatabase style={{ color: '#818cf8' }} />
          <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Total Documents</span>
        </div>
        <div className="stat-number">
          {stats ? stats.total_documents : '--'}
        </div>
      </div>

      <div className="stat-card" style={{ minWidth: 'auto' }}>
        <button className="btn btn-sm" style={{ color: '#94a3b8' }} onClick={fetchStats}>
          <FiRefreshCw /> Refresh
        </button>
      </div>
    </div>
  )
}

export default Dashboard

import React, { useState } from 'react'
import Dashboard from '../components/Dashboard'
import UploadPanel from '../components/UploadPanel'
import ChatInterface from '../components/ChatInterface'

function Home() {
  const [recentStore, setRecentStore] = useState(null)

  return (
    <div className="page-container">
      <div className="mb-4">
        <h2 className="mb-1">Knowledge Base</h2>
        <p style={{ color: '#94a3b8' }}>Store, search, and chat with your multimodal content</p>
      </div>

      <Dashboard />

      <div className="row mt-4">
        <div className="col-lg-5 mb-4">
          <UploadPanel onStored={setRecentStore} />

          {recentStore && (
            <div className="card mt-3">
              <div className="card-body">
                <small style={{ color: '#22c55e' }}>Last stored:</small>
                <p className="mb-1 mt-1">{recentStore.summary}</p>
                <div className="d-flex flex-wrap gap-1">
                  {recentStore.tags?.map((t, i) => (
                    <span key={i} className="badge-tag">{t}</span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="col-lg-7 mb-4">
          <ChatInterface />
        </div>
      </div>
    </div>
  )
}

export default Home

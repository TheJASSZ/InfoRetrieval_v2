import React, { useState } from 'react'
import { FiPlay, FiSquare, FiBookmark, FiEye } from 'react-icons/fi'
import toast from 'react-hot-toast'
import {
  startWatchdog,
  stopWatchdog,
  previewBookmarks,
  syncBookmarks,
} from '../services/api'

function Settings() {
  const [watchDirs, setWatchDirs] = useState('')
  const [watchdogRunning, setWatchdogRunning] = useState(false)
  const [bookmarkPath, setBookmarkPath] = useState('')
  const [bookmarkPreview, setBookmarkPreview] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleStartWatchdog = async () => {
    const dirs = watchDirs.split(',').map(d => d.trim()).filter(Boolean)
    if (dirs.length === 0) {
      toast.error('Enter at least one directory')
      return
    }
    setLoading(true)
    try {
      await startWatchdog(dirs)
      setWatchdogRunning(true)
      toast.success('Watchdog started!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start watchdog')
    } finally {
      setLoading(false)
    }
  }

  const handleStopWatchdog = async () => {
    try {
      await stopWatchdog()
      setWatchdogRunning(false)
      toast.success('Watchdog stopped')
    } catch {
      toast.error('Failed to stop watchdog')
    }
  }

  const handlePreview = async () => {
    setLoading(true)
    try {
      const res = await previewBookmarks(bookmarkPath || undefined)
      setBookmarkPreview(res.data)
      toast.success(`Found ${res.data.total} bookmarks`)
    } catch (err) {
      toast.error('Failed to read bookmarks')
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      const res = await syncBookmarks(bookmarkPath || undefined)
      toast.success(res.data.message)
    } catch (err) {
      toast.error('Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="page-container">
      <h2 className="mb-4">Settings</h2>

      <div className="row">
        {/* Watchdog */}
        <div className="col-lg-6 mb-4">
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              File System Watchdog
              <span style={{
                width: 10, height: 10, borderRadius: '50%',
                background: watchdogRunning ? '#22c55e' : '#64748b',
                display: 'inline-block'
              }} />
            </div>
            <div className="card-body">
              <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
                Automatically ingest new files dropped into watched directories.
              </p>
              <textarea
                className="form-control mb-3"
                rows={3}
                placeholder={"~/Documents/InfoStore/notes\n~/Documents/InfoStore/images"}
                value={watchDirs}
                onChange={(e) => setWatchDirs(e.target.value)}
              />
              <div className="d-flex gap-2">
                <button
                  className="btn btn-primary flex-fill"
                  onClick={handleStartWatchdog}
                  disabled={watchdogRunning || loading}
                >
                  <FiPlay className="me-1" /> Start
                </button>
                <button
                  className="btn btn-outline-danger flex-fill"
                  onClick={handleStopWatchdog}
                  disabled={!watchdogRunning}
                >
                  <FiSquare className="me-1" /> Stop
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Bookmark Sync */}
        <div className="col-lg-6 mb-4">
          <div className="card">
            <div className="card-header">
              <FiBookmark className="me-2" /> Chrome Bookmark Sync
            </div>
            <div className="card-body">
              <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
                Import bookmarks from Chrome and auto-scrape their content.
              </p>
              <input
                type="text"
                className="form-control mb-3"
                placeholder="Custom bookmark path (leave empty for default)"
                value={bookmarkPath}
                onChange={(e) => setBookmarkPath(e.target.value)}
              />
              <div className="d-flex gap-2 mb-3">
                <button className="btn btn-outline-primary flex-fill" onClick={handlePreview} disabled={loading}>
                  <FiEye className="me-1" /> Preview
                </button>
                <button className="btn btn-primary flex-fill" onClick={handleSync} disabled={syncing}>
                  {syncing ? <span className="loading-spinner" /> : <><FiBookmark className="me-1" /> Sync All</>}
                </button>
              </div>

              {bookmarkPreview && (
                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                  <small style={{ color: '#64748b' }}>{bookmarkPreview.total} total bookmarks (showing first 50)</small>
                  {bookmarkPreview.bookmarks.map((bm, i) => (
                    <div key={i} className="d-flex justify-content-between py-1" style={{ borderBottom: '1px solid #334155', fontSize: '0.8rem' }}>
                      <span className="text-truncate" style={{ maxWidth: '60%' }}>{bm.title || 'Untitled'}</span>
                      <span className="text-truncate" style={{ maxWidth: '35%', color: '#64748b' }}>{bm.folder}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings

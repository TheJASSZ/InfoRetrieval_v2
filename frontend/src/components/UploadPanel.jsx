import React, { useState, useRef } from 'react'
import { FiLink, FiFileText, FiImage, FiUpload } from 'react-icons/fi'
import toast from 'react-hot-toast'
import { storeURL, storeText, storeFile } from '../services/api'

function UploadPanel({ onStored }) {
  const [activeTab, setActiveTab] = useState('url')
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const fileRef = useRef(null)

  const handleStoreURL = async (e) => {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true)
    try {
      const res = await storeURL(url.trim())
      toast.success('URL stored successfully!')
      setUrl('')
      onStored?.(res.data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to store URL')
    } finally {
      setLoading(false)
    }
  }

  const handleStoreText = async (e) => {
    e.preventDefault()
    if (!text.trim()) return
    setLoading(true)
    try {
      const res = await storeText(text.trim(), title.trim() || undefined)
      toast.success('Text stored successfully!')
      setText('')
      setTitle('')
      onStored?.(res.data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to store text')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    try {
      const res = await storeFile(file)
      toast.success(`File "${file.name}" stored successfully!`)
      fileRef.current.value = ''
      onStored?.(res.data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to store file')
    } finally {
      setLoading(false)
    }
  }

  const tabs = [
    { key: 'url', icon: <FiLink />, label: 'URL' },
    { key: 'text', icon: <FiFileText />, label: 'Text' },
    { key: 'file', icon: <FiImage />, label: 'File' },
  ]

  return (
    <div className="card">
      <div className="card-header">
        <div className="d-flex gap-2">
          {tabs.map(t => (
            <button
              key={t.key}
              className={`btn btn-sm ${activeTab === t.key ? 'btn-primary' : ''}`}
              style={activeTab !== t.key ? { color: '#94a3b8' } : {}}
              onClick={() => setActiveTab(t.key)}
            >
              {t.icon} <span className="ms-1">{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="card-body">
        {activeTab === 'url' && (
          <form onSubmit={handleStoreURL}>
            <input
              type="url"
              className="form-control mb-3"
              placeholder="https://example.com/article"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="btn btn-primary w-100" disabled={loading || !url.trim()}>
              {loading ? <span className="loading-spinner" /> : <><FiUpload className="me-1" /> Store URL</>}
            </button>
          </form>
        )}

        {activeTab === 'text' && (
          <form onSubmit={handleStoreText}>
            <input
              type="text"
              className="form-control mb-2"
              placeholder="Title (optional)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={loading}
            />
            <textarea
              className="form-control mb-3"
              rows={4}
              placeholder="Paste your text note here..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="btn btn-primary w-100" disabled={loading || !text.trim()}>
              {loading ? <span className="loading-spinner" /> : <><FiUpload className="me-1" /> Store Text</>}
            </button>
          </form>
        )}

        {activeTab === 'file' && (
          <div>
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
              Supports: Images (PNG, JPG), Documents (PDF, DOCX, TXT)
            </p>
            <input
              type="file"
              className="form-control"
              ref={fileRef}
              accept=".png,.jpg,.jpeg,.gif,.webp,.pdf,.docx,.doc,.txt,.md"
              onChange={handleFileUpload}
              disabled={loading}
            />
            {loading && (
              <div className="text-center mt-3">
                <span className="loading-spinner" />
                <span className="ms-2" style={{ color: '#94a3b8' }}>Processing file...</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default UploadPanel

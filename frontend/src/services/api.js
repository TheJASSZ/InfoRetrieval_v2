import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// Store endpoints
export const storeURL = (url) => api.post('/store/url', { url })
export const storeText = (text, title) => api.post('/store/text', { text, title })
export const storeFile = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/store/file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// Search endpoints
export const searchInfo = (query, top_k = 5) =>
  api.post('/search', { query, top_k })

export const chatQuery = (query, top_k = 5) =>
  api.post('/chat', { query, top_k })

// Bookmark endpoints
export const previewBookmarks = (path) =>
  api.get('/bookmarks/preview', { params: path ? { bookmark_path: path } : {} })

export const syncBookmarks = (bookmark_path) =>
  api.post('/bookmarks/sync', { bookmark_path })

// Watchdog endpoints
export const startWatchdog = (directories) =>
  api.post('/watchdog/start', { directories })

export const stopWatchdog = () => api.post('/watchdog/stop')

// Utility endpoints
export const getStats = () => api.get('/stats')
export const deleteEntry = (docId) => api.delete(`/entry/${docId}`)
export const healthCheck = () => api.get('/health')

export default api

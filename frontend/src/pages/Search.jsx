import React, { useState } from 'react'
import SearchBar from '../components/SearchBar'
import ResultCard from '../components/ResultCard'
import toast from 'react-hot-toast'
import { searchInfo, deleteEntry } from '../services/api'

function Search() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')

  const handleSearch = async (q) => {
    setQuery(q)
    setLoading(true)
    try {
      const res = await searchInfo(q, 10)
      setResults(res.data.results)
      if (res.data.results.length === 0) {
        toast('No results found', { icon: 'i' })
      }
    } catch (err) {
      toast.error('Search failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (docId) => {
    try {
      await deleteEntry(docId)
      setResults(prev => prev.filter(r => r.id !== docId))
      toast.success('Entry deleted')
    } catch {
      toast.error('Failed to delete')
    }
  }

  return (
    <div className="page-container">
      <div className="mb-4">
        <h2 className="mb-3">Semantic Search</h2>
        <SearchBar onSearch={handleSearch} loading={loading} />
      </div>

      {query && !loading && (
        <p style={{ color: '#64748b', marginBottom: '1rem' }}>
          {results.length} result{results.length !== 1 ? 's' : ''} for "{query}"
        </p>
      )}

      <div>
        {results.map((item) => (
          <ResultCard key={item.id} item={item} onDelete={handleDelete} />
        ))}
      </div>
    </div>
  )
}

export default Search

import React, { useState } from 'react'
import { FiSearch } from 'react-icons/fi'

function SearchBar({ onSearch, loading, placeholder = "Search your knowledge base..." }) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) onSearch(query.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="d-flex gap-2">
      <div className="input-group">
        <span className="input-group-text" style={{ background: '#334155', border: '1px solid #475569', color: '#94a3b8' }}>
          <FiSearch />
        </span>
        <input
          type="text"
          className="form-control form-control-lg"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
      </div>
      <button type="submit" className="btn btn-primary btn-lg px-4" disabled={loading || !query.trim()}>
        {loading ? <span className="loading-spinner" /> : 'Search'}
      </button>
    </form>
  )
}

export default SearchBar

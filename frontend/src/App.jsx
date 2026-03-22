import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { FiHome, FiSearch, FiSettings, FiDatabase } from 'react-icons/fi'
import Home from './pages/Home'
import Search from './pages/Search'
import Settings from './pages/Settings'

function App() {
  return (
    <>
      <Toaster position="top-right" toastOptions={{
        style: { background: '#1e293b', color: '#f1f5f9', border: '1px solid #475569' }
      }} />

      <nav className="navbar navbar-expand-lg" style={{ background: '#0f172a', borderBottom: '1px solid #475569' }}>
        <div className="container">
          <NavLink className="navbar-brand text-white" to="/">
            <FiDatabase className="me-2" style={{ color: '#818cf8' }} />
            InfoStore v2
          </NavLink>

          <div className="navbar-nav ms-auto d-flex flex-row gap-3">
            <NavLink className="nav-link" to="/">
              <FiHome className="me-1" /> Dashboard
            </NavLink>
            <NavLink className="nav-link" to="/search">
              <FiSearch className="me-1" /> Search
            </NavLink>
            <NavLink className="nav-link" to="/settings">
              <FiSettings className="me-1" /> Settings
            </NavLink>
          </div>
        </div>
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </>
  )
}

export default App

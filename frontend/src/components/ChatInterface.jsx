import React, { useState, useRef, useEffect } from 'react'
import { FiSend } from 'react-icons/fi'
import { chatQuery } from '../services/api'
import ResultCard from './ResultCard'

function ChatInterface() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const query = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: query }])
    setLoading(true)

    try {
      const res = await chatQuery(query)
      setMessages(prev => [...prev, {
        role: 'ai',
        content: res.data.answer,
        sources: res.data.sources,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'ai',
        content: 'Sorry, an error occurred while processing your query.',
        sources: [],
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
      <div className="card-header">AI Chat - Ask your Knowledge Base</div>

      <div className="card-body" style={{ overflowY: 'auto', flex: 1, padding: '1rem' }}>
        {messages.length === 0 && (
          <div className="text-center" style={{ color: '#64748b', marginTop: '4rem' }}>
            <p style={{ fontSize: '1.1rem' }}>Ask questions about your stored content</p>
            <p style={{ fontSize: '0.85rem' }}>Powered by RAG - answers are synthesized from your knowledge base</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`d-flex ${msg.role === 'user' ? 'justify-content-end' : 'justify-content-start'}`}>
              <div className={`chat-bubble ${msg.role === 'user' ? 'chat-user' : 'chat-ai'}`}>
                {msg.content}
              </div>
            </div>

            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 mb-3" style={{ paddingLeft: '0.5rem' }}>
                <small style={{ color: '#64748b' }}>Sources:</small>
                {msg.sources.slice(0, 3).map((s, j) => (
                  <ResultCard key={j} item={s} />
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="d-flex justify-content-start">
            <div className="chat-bubble chat-ai">
              <span className="loading-spinner" /> <span className="ms-2">Thinking...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="card-footer" style={{ background: 'transparent', borderTop: '1px solid #475569' }}>
        <form onSubmit={handleSend} className="d-flex gap-2">
          <input
            type="text"
            className="form-control"
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="btn btn-primary px-3" disabled={loading || !input.trim()}>
            <FiSend />
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatInterface

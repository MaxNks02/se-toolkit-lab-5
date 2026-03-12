import { useState, useEffect, useReducer, FormEvent } from 'react'
import './App.css'
import Dashboard from './Dashboard';

const STORAGE_KEY = 'api_key'

// Types for Items
interface Item {
  id: number
  type: string
  title: string
  created_at: string
}

type Page = 'items' | 'dashboard'

type FetchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; items: Item[] }
  | { status: 'error'; message: string }

type FetchAction =
  | { type: 'fetch_start' }
  | { type: 'fetch_success'; data: Item[] }
  | { type: 'fetch_error'; message: string }

function fetchReducer(_state: FetchState, action: FetchAction): FetchState {
  switch (action.type) {
    case 'fetch_start':
      return { status: 'loading' }
    case 'fetch_success':
      return { status: 'success', items: action.data }
    case 'fetch_error':
      return { status: 'error', message: action.message }
    default:
      return _state
  }
}

function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem(STORAGE_KEY) ?? '',
  )
  const [draft, setDraft] = useState('')
  const [currentPage, setCurrentPage] = useState<Page>('items') // Navigation state
  const [fetchState, dispatch] = useReducer(fetchReducer, { status: 'idle' })

  useEffect(() => {
    if (!token || currentPage !== 'items') return

    dispatch({ type: 'fetch_start' })

    fetch('/api/items/', { // Ensure this matches your Vite proxy or full URL
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: Item[]) => dispatch({ type: 'fetch_success', data }))
      .catch((err: Error) =>
        dispatch({ type: 'fetch_error', message: err.message }),
      )
  }, [token, currentPage])

  function handleConnect(e: FormEvent) {
    e.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed) return
    localStorage.setItem(STORAGE_KEY, trimmed)
    setToken(trimmed)
  }

  function handleDisconnect() {
    localStorage.removeItem(STORAGE_KEY)
    setToken('')
    setDraft('')
    setCurrentPage('items')
  }

  if (!token) {
    return (
      <form className="token-form" onSubmit={handleConnect}>
        <h1>API Key</h1>
        <p>Enter your API key to connect.</p>
        <input
          type="password"
          placeholder="Token"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit">Connect</button>
      </form>
    )
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <nav className="nav-menu">
          {/* Page Toggles */}
          <button
            className={`nav-link ${currentPage === 'items' ? 'active' : ''}`}
            onClick={() => setCurrentPage('items')}
          >
            Items
          </button>
          <button
            className={`nav-link ${currentPage === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentPage('dashboard')}
          >
            Dashboard
          </button>
        </nav>
        <button className="btn-disconnect" onClick={handleDisconnect}>
          Disconnect
        </button>
      </header>

      <main className="app-content">
        {/* Conditional Rendering based on currentPage */}
        {currentPage === 'dashboard' ? (
          <Dashboard />
        ) : (
          <>
            <h1>Items List</h1>
            {fetchState.status === 'loading' && <p>Loading items...</p>}
            {fetchState.status === 'error' && <p className="error">Error: {fetchState.message}</p>}

            {fetchState.status === 'success' && (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Type</th>
                      <th>Title</th>
                      <th>Created At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fetchState.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.id}</td>
                        <td><span className={`badge ${item.type}`}>{item.type}</span></td>
                        <td>{item.title}</td>
                        <td>{new Date(item.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
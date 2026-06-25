import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { profilesApi, comparisonsApi } from './api/client'
import type { SearchProfile } from './types'
import ComparisonTable from './components/ComparisonTable'
import HotelMatching from './pages/HotelMatching'
import SearchPage from './pages/SearchPage'
import './App.css'

function Dashboard() {
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)

  const { data: profilesData, isLoading: profilesLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.list,
  })
  const profiles = Array.isArray(profilesData) ? profilesData : []

  const { data: comparisonsData, isLoading: comparisonsLoading } = useQuery({
    queryKey: ['comparisons', selectedProfileId],
    queryFn: () => comparisonsApi.getByProfile(selectedProfileId!),
    enabled: selectedProfileId !== null,
  })
  const comparisons = Array.isArray(comparisonsData) ? comparisonsData : []

  return (
    <main className="app-main">
      <section className="profile-selector">
        <h2>Направления</h2>
        {profilesLoading ? (
          <p className="loading">Загрузка...</p>
        ) : (
          <div className="profile-list">
            {profiles.map((p: SearchProfile) => (
              <button
                key={p.id}
                className={`profile-btn ${selectedProfileId === p.id ? 'active' : ''}`}
                onClick={() => setSelectedProfileId(p.id)}
              >
                <span className="profile-name">{p.name}</span>
                <span className="profile-meta">
                  {p.departure_city} → {p.country} · {p.nights}н · {p.adults}+{p.children}
                </span>
              </button>
            ))}
            {profiles.length === 0 && (
              <p className="empty">Нет сохранённых направлений</p>
            )}
          </div>
        )}
      </section>

      <section className="comparison-section">
        {selectedProfileId === null ? (
          <div className="placeholder">
            <p>Выберите направление слева, чтобы увидеть сравнение цен</p>
          </div>
        ) : comparisonsLoading ? (
          <p className="loading">Загрузка цен...</p>
        ) : (
          <ComparisonTable rows={comparisons} />
        )}
      </section>
    </main>
  )
}

function NavBar() {
  const location = useLocation()
  return (
    <nav className="app-nav">
      <Link to="/search" className={location.pathname === '/search' ? 'active' : ''}>Поиск</Link>
      <Link to="/" className={location.pathname === '/' ? 'active' : ''}>Дашборд</Link>
      <Link to="/hotel-matching" className={location.pathname === '/hotel-matching' ? 'active' : ''}>
        Сопоставление отелей
      </Link>
    </nav>
  )
}

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>TourPrice</h1>
        <span className="app-subtitle">Мониторинг цен туроператоров</span>
        <NavBar />
      </header>

      <Routes>
        <Route path="/search" element={<SearchPage />} />
        <Route path="/" element={<Dashboard />} />
        <Route path="/hotel-matching" element={<HotelMatching />} />
      </Routes>
    </div>
  )
}
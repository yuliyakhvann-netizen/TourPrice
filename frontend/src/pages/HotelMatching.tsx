import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { hotelMappingsApi } from '../api/client'
import { OPERATOR_NAMES } from '../types'
import './HotelMatching.css'

type Tab = 'pending' | 'auto' | 'stats'

export default function HotelMatching() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('pending')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ['hotel-pending'],
    queryFn: hotelMappingsApi.getPending,
  })
  const pending = Array.isArray(pendingData) ? pendingData : []

  const { data: suggestionsData, isLoading: suggestionsLoading } = useQuery({
    queryKey: ['hotel-suggestions', selectedId],
    queryFn: () => hotelMappingsApi.getSuggestions(selectedId!),
    enabled: selectedId !== null && tab === 'pending',
  })
  const suggestions = Array.isArray(suggestionsData) ? suggestionsData : []

  const { data: confirmedData, isLoading: confirmedLoading, refetch: refetchConfirmed } = useQuery({
    queryKey: ['hotel-confirmed'],
    queryFn: hotelMappingsApi.getConfirmed,
    enabled: tab === 'auto' || tab === 'stats',
  })
  const confirmedGroups = Array.isArray(confirmedData) ? confirmedData : []
  const autoGroups = confirmedGroups.filter((g: any) => g.hotels.some((h: any) => h.auto_matched))
  const manualGroups = confirmedGroups.filter((g: any) => !g.hotels.some((h: any) => h.auto_matched))

  const mergeMutation = useMutation({
    mutationFn: ({ id, targetId }: { id: number; targetId: number }) =>
      hotelMappingsApi.merge(id, targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-pending'] })
      setSelectedId(null)
    },
  })

  const confirmNew = useMutation({
    mutationFn: (id: number) => hotelMappingsApi.confirmAsNew(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-pending'] })
      setSelectedId(null)
    },
  })

  const unmatchMutation = useMutation({
    mutationFn: (id: number) => hotelMappingsApi.unmatch(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-confirmed'] })
      queryClient.invalidateQueries({ queryKey: ['hotel-pending'] })
    },
  })

  const autoMatchMutation = useMutation({
    mutationFn: () => hotelMappingsApi.runAutoMatch(90),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-pending'] })
      queryClient.invalidateQueries({ queryKey: ['hotel-confirmed'] })
    },
  })

  const selected = pending.find(p => p.id === selectedId) ?? null

  return (
    <div className="hm-wrap">
      <div className="hm-header">
        <h1 className="hm-title">Сопоставление отелей</h1>
        <div className="hm-tabs">
          <button className={`hm-tab ${tab === 'pending' ? 'active' : ''}`} onClick={() => setTab('pending')}>
            Ручной матч <span className="hm-count">{pending.length}</span>
          </button>
          <button className={`hm-tab ${tab === 'auto' ? 'active' : ''}`} onClick={() => { setTab('auto'); refetchConfirmed() }}>
            Авто-матч <span className="hm-count hm-count-auto">{autoGroups.length}</span>
          </button>
          <button className={`hm-tab ${tab === 'stats' ? 'active' : ''}`} onClick={() => setTab('stats')}>
            Статистика
          </button>
        </div>
        <button className="hm-auto-btn" onClick={() => autoMatchMutation.mutate()} disabled={autoMatchMutation.isPending}>
          {autoMatchMutation.isPending ? '⏳ Запускаем...' : '⚡ Авто-матч 90%'}
        </button>
      </div>

      {tab === 'pending' && (
        <div className="hm">
          <div className="hm-list">
            <h2>Несопоставленные отели <span className="hm-count">{pending.length}</span></h2>
            {pendingLoading ? <p className="loading">Загрузка...</p> : pending.length === 0 ? (
              <p className="empty">Все отели сопоставлены 🎉</p>
            ) : (
              <ul className="hm-items">
                {pending.map(p => (
                  <li key={p.id} className={`hm-item ${selectedId === p.id ? 'active' : ''}`} onClick={() => setSelectedId(p.id)}>
                    <span className="hm-operator">{OPERATOR_NAMES[p.operator_id] ?? `op${p.operator_id}`}</span>
                    <span className="hm-name">{p.raw_value}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="hm-detail">
            {selected === null ? (
              <p className="placeholder">Выберите отель слева, чтобы найти совпадения</p>
            ) : (
              <>
                <div className="hm-target">
                  <span className="hm-target-label">Сопоставляем:</span>
                  <span className="hm-target-operator">{OPERATOR_NAMES[selected.operator_id]}</span>
                  <span className="hm-target-name">{selected.raw_value}</span>
                </div>
                <h3>Похожие отели у других операторов</h3>
                {suggestionsLoading ? <p className="loading">Поиск похожих...</p> : suggestions.length === 0 ? (
                  <p className="empty">Похожих отелей не найдено</p>
                ) : (
                  <ul className="hm-suggestions">
                    {suggestions.map(s => (
                      <li key={s.hotel_mapping_id} className="hm-suggestion">
                        <div className="hm-suggestion-info">
                          <span className="hm-operator">{OPERATOR_NAMES[s.operator_id] ?? `op${s.operator_id}`}</span>
                          <span className="hm-name">{s.raw_value}</span>
                          <span className="hm-score">{s.score.toFixed(0)}% совпадение</span>
                        </div>
                        <button className="btn-primary" disabled={mergeMutation.isPending}
                          onClick={() => mergeMutation.mutate({ id: selected.id, targetId: s.hotel_mapping_id })}>
                          Это тот же отель
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="hm-new">
                  <p>Не нашли совпадение?</p>
                  <button className="btn-secondary" disabled={confirmNew.isPending} onClick={() => confirmNew.mutate(selected.id)}>
                    Отметить как новый отель
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'auto' && (
        <div className="hm-auto-wrap">
          {confirmedLoading ? <p className="loading">Загрузка...</p> : autoGroups.length === 0 ? (
            <p className="empty">Нет авто-сопоставленных групп. Нажмите «Авто-матч 90%».</p>
          ) : (
            <>
              <p className="hm-auto-hint">
                ⚠️ Проверьте группы — если отели разные, нажмите «Разъединить». Вручную подтверждённые помечены иначе.
              </p>
              <div className="hm-auto-groups">
                {autoGroups.map((group: any) => (
                  <div key={group.canonical_hotel_id} className="hm-auto-group">
                    <div className="hm-auto-group-id">Группа #{group.canonical_hotel_id}</div>
                    {group.hotels.map((h: any) => (
                      <div key={h.id} className="hm-auto-hotel">
                        <div className="hm-auto-hotel-info">
                          <span className="hm-operator">{OPERATOR_NAMES[h.operator_id] ?? `op${h.operator_id}`}</span>
                          <span className="hm-name">{h.raw_value}</span>
                          {h.auto_matched && <span className="hm-auto-badge">авто</span>}
                        </div>
                        <button className="btn-danger" onClick={() => unmatchMutation.mutate(h.id)} disabled={unmatchMutation.isPending}>
                          Разъединить
                        </button>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'stats' && (
        <div className="hm-stats">
          <div className="hm-stat-card">
            <div className="hm-stat-value">{pending.length}</div>
            <div className="hm-stat-label">Ожидают ручного матча</div>
          </div>
          <div className="hm-stat-card hm-stat-auto">
            <div className="hm-stat-value">{autoGroups.length}</div>
            <div className="hm-stat-label">Авто-сопоставленных групп</div>
          </div>
          <div className="hm-stat-card hm-stat-ok">
            <div className="hm-stat-value">{manualGroups.length}</div>
            <div className="hm-stat-label">Подтверждено вручную</div>
          </div>
          <div className="hm-stat-card hm-stat-total">
            <div className="hm-stat-value">{confirmedGroups.length}</div>
            <div className="hm-stat-label">Всего canonical групп</div>
          </div>
        </div>
      )}
    </div>
  )
}

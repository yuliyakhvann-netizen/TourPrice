import React, { useState, useEffect } from 'react'
import { searchApi, locationsApi } from '../api/client'
import type { DualSearchRequest, DualSearchTourResult } from '../types'
import MultiSelect from '../components/MultiSelect'
import * as XLSX from 'xlsx'
import './SearchPage.css'

const OPERATORS_ORDER = ['funsun', 'kompas', 'pegas', 'selfie', 'kazunion']
const BASELINE_OPERATOR = 'funsun'
const OPERATOR_LABELS: Record<string, string> = {
  kompas: 'Kompas',
  pegas: 'Pegas',
  selfie: 'Selfie',
  funsun: 'Fun&Sun',
  kazunion: 'Kazunion',
}

function fmt(val: number | null) {
  if (val === null) return '—'
  return Math.round(val).toLocaleString('ru-RU')
}

function fmtDiff(val: number | null) {
  if (val === null) return '—'
  const rounded = Math.round(val)
  return rounded.toLocaleString('ru-RU')
}

function fmtVsBaseline(val: number | null) {
  if (val === null) return '—'
  const rounded = Math.round(val)
  if (rounded === 0) return '='
  const sign = rounded > 0 ? '+' : ''
  return sign + rounded.toLocaleString('ru-RU')
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function addDays(dateStr: string, days: number) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function SearchPage() {
  const today = todayStr()
  const [form, setForm] = useState<DualSearchRequest>({
    country: 'Вьетнам',
    departure_city: 'Алматы',
    checkin_beg: addDays(today, 1),
    checkin_end: addDays(today, 14),
    nights_from: 7,
    nights_till: 7,
    adults: 2,
    child_age: 4,
  })

  const [filterHotels, setFilterHotels] = useState<string[]>([])
  const [filterMeals, setFilterMeals] = useState<string[]>([])
  const [filterRooms, setFilterRooms] = useState<string[]>([])
  const [selectedResorts, setSelectedResorts] = useState<string[]>([])
  const [selectedOperators, setSelectedOperators] = useState<string[]>(OPERATORS_ORDER)

  const [sortKey, setSortKey] = useState<string>('departure_date')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const [results, setResults] = useState<DualSearchTourResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)
  const [countries, setCountries] = useState<string[]>(['Вьетнам'])
  const [departureCities, setDepartureCities] = useState<string[]>(['Алматы'])
  const [resorts, setResorts] = useState<string[]>([])

  useEffect(() => {
    locationsApi.getCountries()
      .then(data => {
        if (data.length > 0) {
          setCountries(data)
          set('country', data.includes('Вьетнам') ? 'Вьетнам' : data[0])
        }
      })
      .catch(() => {})
    locationsApi.getDepartureCities()
      .then(data => setDepartureCities(data.length > 0 ? data : ['Алматы']))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!form.country) return
    setSelectedResorts([])
    locationsApi.getResorts(form.country)
      .then(data => setResorts(data))
      .catch(() => setResorts([]))
  }, [form.country])

  const withChild = true

  function set<K extends keyof DualSearchRequest>(k: K, v: DualSearchRequest[K]) {
    setForm(prev => ({ ...prev, [k]: v }))
  }

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  function getSortValue(row: DualSearchTourResult, key: string): number | string {
    if (key === 'hotel') return row.hotel
    if (key === 'departure_date') return row.departure_date
    if (key === 'nights') return row.nights
    const parts = key.split('_')
    const field = parts[parts.length - 1]
    const opCode = parts.slice(0, -1).join('_')
    const op = row.operators.find(o => o.operator_code === opCode)
    if (!op) return Infinity
    if (field === 'adults') return Number(op.price_adults_only ?? Infinity)
    if (field === 'child') return Number(op.price_with_child ?? Infinity)
    if (field === 'diff') return Number(op.child_diff ?? Infinity)
    return Infinity
  }

  async function handleSearch() {
    setLoading(true)
    setError(null)
    setResults([])
    setSearched(true)
    setFilterHotels([])
    setFilterMeals([])
    setFilterRooms([])
    try {
      const data = await searchApi.dual(form)
      setResults(data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка поиска')
    } finally {
      setLoading(false)
    }
  }

  function exportCsv() {
    const headers: string[] = ['Отель', 'Питание', 'Дата', 'Ночей']
    for (const code of operatorCodes) {
      const label = OPERATOR_LABELS[code] ?? code
      headers.push(`${label} 2 взр`, `${label} +реб`, `${label} разн`)
    }
    const csvRows: string[] = [headers.join(';')]
    for (const r of sortedAndFiltered) {
      const opMap = Object.fromEntries(r.operators.map(op => [op.operator_code, op]))
      const cells: string[] = [r.hotel, r.meal_type, r.departure_date, String(r.nights)]
      for (const code of operatorCodes) {
        const op = opMap[code]
        cells.push(
          op?.price_adults_only != null ? String(Math.round(op.price_adults_only)) : '',
          op?.price_with_child != null ? String(Math.round(op.price_with_child)) : '',
          op?.child_diff != null ? String(Math.round(op.child_diff)) : '',
        )
      }
      csvRows.push(cells.join(';'))
    }
    const bom = '\uFEFF'
    const blob = new Blob([bom + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `tourprice_${form.country}_${form.checkin_beg}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  function exportXlsx() {
    const wb = XLSX.utils.book_new()

    // Заголовки — два уровня
    const headers1: string[] = ['Отель', 'Питание', 'Дата', 'Ночей']
    const headers2: string[] = ['', '', '', '']
    for (const code of operatorCodes) {
      const label = OPERATOR_LABELS[code] ?? code
      headers1.push(label, '', '')
      headers2.push('2 взр', '+реб', 'разн')
    }

    const rows: any[][] = []
    rows.push(headers1)
    rows.push(headers2)

    for (const r of sortedAndFiltered) {
      const opMap = Object.fromEntries(r.operators.map(op => [op.operator_code, op]))
      const row: any[] = [r.hotel, r.meal_type, r.departure_date, r.nights]
      for (const code of operatorCodes) {
        const op = opMap[code]
        row.push(
          op?.price_adults_only != null ? Math.round(op.price_adults_only) : null,
          op?.price_with_child != null ? Math.round(op.price_with_child) : null,
          op?.child_diff != null ? Math.round(op.child_diff) : null,
        )
      }
      rows.push(row)
    }

    const ws = XLSX.utils.aoa_to_sheet(rows)

    // Ширина колонок
    ws['!cols'] = [
      { wch: 40 }, // Отель
      { wch: 16 }, // Питание
      { wch: 12 }, // Дата
      { wch: 7 },  // Ночей
      ...operatorCodes.flatMap(() => [{ wch: 12 }, { wch: 12 }, { wch: 10 }]),
    ]

    // Подсветка разницы — оранжевый если diff > 0
    const diffColIndices: number[] = []
    operatorCodes.forEach((_, i) => diffColIndices.push(4 + i * 3 + 2))

    for (let rowIdx = 2; rowIdx < rows.length; rowIdx++) {
      for (const colIdx of diffColIndices) {
        const cellAddr = XLSX.utils.encode_cell({ r: rowIdx, c: colIdx })
        const cell = ws[cellAddr]
        if (cell && typeof cell.v === 'number' && cell.v > 0) {
          cell.s = {
            fill: { patternType: 'solid', fgColor: { rgb: 'FFF3CD' } },
            font: { color: { rgb: 'B45309' } },
          }
        }
      }
    }

    // Объединяем заголовки операторов
    ws['!merges'] = []
    operatorCodes.forEach((_, i) => {
      const col = 4 + i * 3
      ws['!merges']!.push({ s: { r: 0, c: col }, e: { r: 0, c: col + 2 } })
    })

    // Стиль заголовков
    for (let c = 0; c < headers1.length; c++) {
      const cellAddr = XLSX.utils.encode_cell({ r: 0, c })
      if (!ws[cellAddr]) continue
      ws[cellAddr].s = {
        fill: { patternType: 'solid', fgColor: { rgb: '1E3A5F' } },
        font: { color: { rgb: 'FFFFFF' }, bold: true },
        alignment: { horizontal: 'center' },
      }
    }
    for (let c = 0; c < headers2.length; c++) {
      const cellAddr = XLSX.utils.encode_cell({ r: 1, c })
      if (!ws[cellAddr]) continue
      ws[cellAddr].s = {
        fill: { patternType: 'solid', fgColor: { rgb: '2563EB' } },
        font: { color: { rgb: 'FFFFFF' }, bold: false },
        alignment: { horizontal: 'center' },
      }
    }

    XLSX.utils.book_append_sheet(wb, ws, form.country)
    XLSX.writeFile(wb, `tourprice_${form.country}_${form.checkin_beg}.xlsx`)
  }

  const allOperatorCodes = OPERATORS_ORDER.filter(code =>
    results.some(r => r.operators.some(op => op.operator_code === code))
  )
  const operatorCodes = allOperatorCodes.filter(code => selectedOperators.includes(code))

  const sortedAndFiltered = [...results]
    .filter(r => {
      if (selectedResorts.length > 0 && !selectedResorts.includes(r.resort)) return false
      if (filterHotels.length > 0 && !filterHotels.includes(r.hotel)) return false
      if (filterMeals.length > 0 && !filterMeals.includes(r.meal_type)) return false
      if (filterRooms.length > 0 && !filterRooms.includes(r.room_type)) return false
      // Показываем строку только если хотя бы один видимый оператор имеет цену
      const hasPrice = operatorCodes.some(code => {
        const op = r.operators.find(o => o.operator_code === code)
        return op && (op.price_adults_only != null || op.price_with_child != null)
      })
      return hasPrice
    })
    .sort((a, b) => {
      const av = getSortValue(a, sortKey)
      const bv = getSortValue(b, sortKey)
      if (av === bv) return 0
      if (av === Infinity) return 1
      if (bv === Infinity) return -1
      const cmp = av < bv ? -1 : 1
      return sortDir === 'asc' ? cmp : -cmp
    })

  const arrow = (key: string) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''

  const hasActiveFilters = filterMeals.length > 0 || filterRooms.length > 0 || filterHotels.length > 0

  return (
    <div className="sp-wrap">
      <div className="sp-form">
        <div className="sp-form-row">
          <label>
            <span>Страна</span>
            <select value={form.country} onChange={e => set('country', e.target.value)}>
              {countries.map(c => <option key={c}>{c}</option>)}
            </select>
          </label>
          <MultiSelect
            label="Город прибытия"
            options={resorts}
            selected={selectedResorts}
            onChange={setSelectedResorts}
            placeholder="Все города"
          />
          <label>
            <span>Город вылета</span>
            <select value={form.departure_city} onChange={e => set('departure_city', e.target.value)}>
              {departureCities.map(city => <option key={city} value={city}>{city}</option>)}
            </select>
          </label>
          <label>
            <span>Вылет от</span>
            <input type="date" value={form.checkin_beg} onChange={e => set('checkin_beg', e.target.value)} />
          </label>
          <label>
            <span>до</span>
            <input type="date" value={form.checkin_end} onChange={e => set('checkin_end', e.target.value)} />
          </label>
          <label>
            <span>Ночей от</span>
            <select value={form.nights_from} onChange={e => set('nights_from', Number(e.target.value))}>
              {[5,6,7,8,9,10,11,12,14].map(n => <option key={n}>{n}</option>)}
            </select>
          </label>
          <label>
            <span>до</span>
            <select value={form.nights_till} onChange={e => set('nights_till', Number(e.target.value))}>
              {[5,6,7,8,9,10,11,12,14].map(n => <option key={n}>{n}</option>)}
            </select>
          </label>
          <button className="sp-search-btn" onClick={handleSearch} disabled={loading}>
            {loading ? 'Ищем...' : '🔍 Найти'}
          </button>
          {results.length > 0 && (
            <>
              <button className="sp-export-btn" onClick={exportCsv}>📥 CSV</button>
              <button className="sp-export-btn sp-export-xlsx" onClick={exportXlsx}>📊 Excel</button>
            </>
          )}
        </div>
        <div className="sp-operators-row">
          <span className="sp-filter-ops-label">Операторы:</span>
          {OPERATORS_ORDER.map(code => (
            <label key={code} className="sp-op-toggle">
              <input
                type="checkbox"
                checked={selectedOperators.includes(code)}
                onChange={() => setSelectedOperators(prev =>
                  prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
                )}
              />
              {OPERATOR_LABELS[code] ?? code}
            </label>
          ))}
        </div>
      </div>

      {loading && <div className="sp-status">Запрашиваем цены у операторов, это займёт ~1 минуту...</div>}
      {error && <div className="sp-error">{error}</div>}
      {!loading && searched && results.length === 0 && !error && <div className="sp-status">Результатов не найдено</div>}

      {results.length > 0 && (
        <>
          <div className="sp-filters">
            <MultiSelect
              label="Питание"
              options={[...new Set(results.map(r => r.meal_type))].sort()}
              selected={filterMeals}
              onChange={setFilterMeals}
              placeholder="Все"
            />
            <MultiSelect
              label="Тип номера"
              options={[...new Set(results.map(r => r.room_type))].sort()}
              selected={filterRooms}
              onChange={setFilterRooms}
              placeholder="Все"
            />
            <MultiSelect
              label="Отель"
              options={[...new Set(results.map(r => r.hotel))].sort()}
              selected={filterHotels}
              onChange={setFilterHotels}
              placeholder="Все"
            />
            {hasActiveFilters && (
              <button className="sp-clear-btn" onClick={() => { setFilterMeals([]); setFilterRooms([]); setFilterHotels([]) }}>
                ✕ Сбросить
              </button>
            )}
          </div>

          <div className="sp-table-wrap">
            <p className="sp-meta">{sortedAndFiltered.length} из {results.length} вариантов</p>
            <table className="sp-table">
              <thead>
                <tr>
                  <th rowSpan={2} onClick={() => handleSort('hotel')} style={{cursor:'pointer'}}>Отель{arrow('hotel')}</th>
                  <th rowSpan={2}>Питание</th>
                  <th rowSpan={2} onClick={() => handleSort('departure_date')} style={{cursor:'pointer'}}>Дата{arrow('departure_date')}</th>
                  <th rowSpan={2} onClick={() => handleSort('nights')} style={{cursor:'pointer'}}>Ночей{arrow('nights')}</th>
                  {operatorCodes.map(code => (
                    <th key={code} colSpan={withChild ? 3 : 1} className="op-header">
                      {OPERATOR_LABELS[code] ?? code}
                    </th>
                  ))}
                </tr>
                {withChild && (
                  <tr>
                    {operatorCodes.map(code => (
                      <React.Fragment key={code}>
                        <th className="subh" onClick={() => handleSort(`${code}_adults`)} style={{cursor:'pointer'}}>2 взр{arrow(`${code}_adults`)}</th>
                        <th className="subh" onClick={() => handleSort(`${code}_child`)} style={{cursor:'pointer'}}>+реб{arrow(`${code}_child`)}</th>
                        {code === BASELINE_OPERATOR
                          ? <th className="subh diff-h">разн.</th>
                          : <th className="subh diff-h vs-baseline-h" onClick={() => handleSort(`${code}_vs`)} style={{cursor:'pointer'}}>vs FS{arrow(`${code}_vs`)}</th>
                        }
                      </React.Fragment>
                    ))}
                  </tr>
                )}
              </thead>
              <tbody>
                {sortedAndFiltered.map((row, i) => {
                  const opMap = Object.fromEntries(row.operators.map(op => [op.operator_code, op]))
                  return (
                    <tr key={i}>
                      <td className="hotel-cell">{row.hotel}</td>
                      <td>{row.meal_type}</td>
                      <td className="date-cell">{row.departure_date}</td>
                      <td className="c">{row.nights}</td>
                      {operatorCodes.map(code => {
                        const op = opMap[code]
                        const baseline = opMap[BASELINE_OPERATOR]
                        const vsAdults = (code !== BASELINE_OPERATOR && op?.price_adults_only != null && baseline?.price_adults_only != null)
                          ? op.price_adults_only - baseline.price_adults_only
                          : null
                        return (
                          <React.Fragment key={code}>
                            <td className="price-cell">{op ? fmt(op.price_adults_only) : '—'}</td>
                            <td className="price-cell">{op ? fmt(op.price_with_child) : '—'}</td>
                            {code === BASELINE_OPERATOR
                              ? <td className={`price-cell diff-cell ${op?.child_diff != null && op.child_diff > 0 ? 'diff-pos' : ''}`}>{op ? fmtDiff(op.child_diff) : '—'}</td>
                              : <td className={`price-cell diff-cell ${vsAdults != null && vsAdults < 0 ? 'diff-neg' : vsAdults != null && vsAdults > 0 ? 'diff-pos' : ''}`}>{fmtVsBaseline(vsAdults)}</td>
                            }
                          </React.Fragment>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
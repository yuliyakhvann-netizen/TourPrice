import { useState, useRef, useEffect } from 'react'
import './MultiSelect.css'

interface Props {
  label: string
  options: string[]
  selected: string[]
  onChange: (values: string[]) => void
  placeholder?: string
}

export default function MultiSelect({ label, options, selected, onChange, placeholder }: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const filtered = options.filter(o =>
    o.toLowerCase().includes(search.toLowerCase())
  )

  function toggle(val: string) {
    if (selected.includes(val)) {
      onChange(selected.filter(v => v !== val))
    } else {
      onChange([...selected, val])
    }
  }

  function toggleAll() {
    if (selected.length === options.length) {
      onChange([])
    } else {
      onChange([...options])
    }
  }

  const displayText = selected.length === 0
    ? (placeholder ?? 'Все')
    : selected.length === options.length
    ? 'Все'
    : selected.join(', ')

  return (
    <div className="ms-wrap" ref={ref}>
      <span className="ms-label">{label}</span>
      <div
        className={`ms-trigger ${open ? 'open' : ''}`}
        onClick={() => setOpen(o => !o)}
      >
        <span className="ms-value" title={displayText}>{displayText}</span>
        <span className="ms-arrow">{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div className="ms-dropdown">
          {options.length > 5 && (
            <input
              className="ms-search"
              placeholder="Поиск..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              onClick={e => e.stopPropagation()}
              autoFocus
            />
          )}
          <div className="ms-option ms-all" onClick={toggleAll}>
            <input
              type="checkbox"
              readOnly
              checked={selected.length === options.length}
              ref={el => {
                if (el) el.indeterminate = selected.length > 0 && selected.length < options.length
              }}
            />
            <span>Все</span>
          </div>
          <div className="ms-list">
            {filtered.map(opt => (
              <div key={opt} className="ms-option" onClick={() => toggle(opt)}>
                <input type="checkbox" readOnly checked={selected.includes(opt)} />
                <span>{opt}</span>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="ms-empty">Ничего не найдено</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
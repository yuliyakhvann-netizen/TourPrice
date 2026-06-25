import type { ComparisonResult } from '../types'
import './ComparisonTable.css'

const OPERATORS = [
  { key: 'funsun_price', label: 'Fun&Sun' },
  { key: 'kompas_price', label: 'Kompas' },
  { key: 'pegas_price', label: 'Pegas' },
  { key: 'anex_price', label: 'Anex' },
] as const

function fmt(val: number | null, currency: string) {
  if (val === null) return <span className="no-price">—</span>
  return <span>{val.toLocaleString('ru-RU')} {currency}</span>
}

function minMark(val: number | null, min: number | null) {
  if (val === null || min === null) return ''
  return val === min ? ' best' : ''
}

interface Props { rows: ComparisonResult[] }

export default function ComparisonTable({ rows }: Props) {
  if (rows.length === 0) {
    return <p className="empty">Нет данных для сравнения. Запустите сбор данных.</p>
  }

  return (
    <div className="ct-wrap">
      <p className="ct-meta">
        Обновлено: {new Date(rows[0].created_at).toLocaleString('ru-RU')} ·{' '}
        {rows.length} вариантов
      </p>
      <table className="ct">
        <thead>
          <tr>
            <th>Отель</th>
            <th>Номер</th>
            <th>Питание</th>
            <th className="c">Ночей</th>
            {OPERATORS.map(op => (
              <th key={op.key} className="c">{op.label}</th>
            ))}
            <th className="c">Мин. рынок</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.tour_key}>
              <td className="hotel">{row.hotel}</td>
              <td>{row.room_type}</td>
              <td>{row.meal_type}</td>
              <td className="c">{row.nights}</td>
              {OPERATORS.map(op => (
                <td key={op.key} className={`c price${minMark(row[op.key], row.market_min_price)}`}>
                  {fmt(row[op.key], row.currency)}
                </td>
              ))}
              <td className="c price-min">
                {fmt(row.market_min_price, row.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
export interface SearchProfile {
  id: number
  name: string
  country: string
  departure_city: string
  departure_date: string
  nights: number
  adults: number
  children: number
  is_active: boolean
}

export interface ComparisonResult {
  id: number
  profile_id: number
  tour_key: string
  scrape_run_id: string
  hotel: string
  room_type: string
  meal_type: string
  airline: string
  nights: number
  funsun_price: number | null
  pegas_price: number | null
  anex_price: number | null
  kompas_price: number | null
  market_min_price: number | null
  market_max_price: number | null
  market_avg_price: number | null
  currency: string
  created_at: string
}

export interface PriceHistoryPoint {
  operator_code: string
  price: number
  currency: string
  recorded_at: string
}

export interface HotelMapping {
  id: number
  operator_id: number
  raw_value: string
  canonical_hotel_id: number | null
  confirmed: boolean
  created_at: string
  confirmed_at: string | null
}

export interface HotelSuggestion {
  hotel_mapping_id: number
  operator_id: number
  raw_value: string
  canonical_hotel_id: number | null
  confirmed: boolean
  score: number
}

// Matches the operators table seed order (id 1=funsun, 2=pegas, 3=anex, 4=kompas).
// Not fetched dynamically since it almost never changes and avoids an extra request
// on every render of the hotel-matching page.
export const OPERATOR_NAMES: Record<number, string> = {
  1: 'Fun&Sun',
  2: 'Pegas',
  3: 'Anex',
  4: 'Kompas',
  6: 'Selfie',
  7: 'Kazunion',
}

export interface DualSearchRequest {
  country: string
  departure_city: string
  checkin_beg: string   // YYYY-MM-DD
  checkin_end: string
  nights_from: number
  nights_till: number
  adults: number
  child_age: number     // 0 = без ребёнка, иначе возраст
}

export interface OperatorDualPrice {
  operator_code: string
  price_adults_only: number | null
  price_with_child: number | null
  child_diff: number | null
}

export interface DualSearchTourResult {
  hotel: string
  resort: string
  room_type: string
  meal_type: string
  departure_date: string
  nights: number
  operators: OperatorDualPrice[]
}
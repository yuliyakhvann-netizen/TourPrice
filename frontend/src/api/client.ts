import axios from 'axios'
import type {
  SearchProfile,
  ComparisonResult,
  PriceHistoryPoint,
  HotelMapping,
  HotelSuggestion,
  DualSearchRequest,
  DualSearchTourResult,
} from '../types'

const api = axios.create({ baseURL: '/api/v1' })

export const profilesApi = {
  list: () => api.get<SearchProfile[]>('/profiles/').then(r => r.data),
  create: (data: Omit<SearchProfile, 'id' | 'is_active'>) =>
    api.post<SearchProfile>('/profiles/', data).then(r => r.data),
}

export const comparisonsApi = {
  getByProfile: (profile_id: number) =>
    api.get<ComparisonResult[]>('/comparisons/', { params: { profile_id } }).then(r => r.data),
  getHistory: (tour_key: string, limit = 50) =>
    api.get<PriceHistoryPoint[]>('/comparisons/history', { params: { tour_key, limit } }).then(r => r.data),
}

export const hotelMappingsApi = {
  getPending: () => api.get<HotelMapping[]>('/mappings/hotels/pending').then(r => r.data),
  getSuggestions: (id: number) =>
    api.get<HotelSuggestion[]>(`/mappings/hotels/${id}/suggestions`).then(r => r.data),
  merge: (id: number, target_id: number) =>
    api.patch(`/mappings/hotels/${id}/merge`, { target_id }).then(r => r.data),
  confirmAsNew: (id: number) =>
    api.patch(`/mappings/hotels/${id}/confirm`, { canonical_hotel_id: null }).then(r => r.data),
  unmatch: (id: number) =>
    api.patch(`/mappings/hotels/${id}/unmatch`).then(r => r.data),
  getConfirmed: () =>
    api.get('/mappings/hotels/confirmed').then(r => r.data),
  runAutoMatch: (threshold: number) =>
    api.post(`/mappings/hotels/auto-match/run?threshold=${threshold}`).then(r => r.data),
}

export const searchApi = {
  dual: (data: DualSearchRequest) =>
    api.post<DualSearchTourResult[]>('/search/dual', data).then(r => r.data),
}

export const locationsApi = {
  getDepartureCities: () =>
    api.get<string[]>('/operators/departure-cities').then(r => r.data),
  getResorts: (country: string) =>
    api.get<string[]>('/operators/resorts', { params: { country } }).then(r => r.data),
  getCountries: () =>
    api.get<string[]>('/operators/countries').then(r => r.data),
}
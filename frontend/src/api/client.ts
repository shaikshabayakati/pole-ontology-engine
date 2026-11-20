import axios from 'axios';
import type { Graph, Job, RecordDocument, Review, SearchResult, Status } from '../types';

const baseURL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const http = axios.create({ baseURL });
export const sampleURL = baseURL + '/api/documents/sample.pdf';

export const api = {
  status: () => http.get<Status>('/api/status').then(({ data }) => data),
  graph: () => http.get<Graph>('/api/graph').then(({ data }) => data),
  path: (source_id: string, target_id: string) => http.get<Graph>('/api/graph/shortest-path', { params: { source_id, target_id } }).then(({ data }) => data),
  query: (question: string, history: string[], pending_question?: string, selected_id?: string, previous_person?: string, previous_cases?: string[]) =>
    http.post<SearchResult>('/api/query', { question, history, pending_question, selected_id, previous_person, previous_cases }).then(({ data }) => data),
  document: (id: string, signal: AbortSignal) => http.get<RecordDocument>('/api/documents/' + encodeURIComponent(id), { signal }).then(({ data }) => data),
  reviews: () => http.get<Review[]>('/api/reviews').then(({ data }) => data),
  decide: (id: string, decision: 'approve' | 'reject') => http.post<Review>('/api/reviews/' + encodeURIComponent(id), { decision }).then(({ data }) => data),
  upload: (file: File, documentType: string, station: string) => {
    const form = new FormData();
    form.set('file', file);
    form.set('document_type', documentType);
    form.set('police_station', station);
    return http.post<{ job_id: string }>('/api/documents/upload?queued=true', form).then(({ data }) => data.job_id);
  },
  job: (id: string) => http.get<Job>('/api/uploads/' + encodeURIComponent(id)).then(({ data }) => data),
};

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ');
    if (!error.response) return 'Could not reach the backend at ' + baseURL + '.';
  }
  return error instanceof Error ? error.message : 'The request failed.';
}

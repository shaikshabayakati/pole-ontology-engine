import { CircleAlert, Moon, Sun, ClipboardList, Columns2, Network, Search } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api, errorMessage } from './api/client';
import GraphExplorer from './components/GraphExplorer';
import HitlReviewPanel from './components/HitlReviewPanel';
import Navbar, { Brand, StorageStatus, type View } from './components/Navbar';
import PdfUploadModal from './components/PdfUploadModal';
import SearchChatPanel from './components/SearchChatPanel';
import SourceViewerDrawer from './components/SourceViewerDrawer';
import type { ChatTurn, Citation, Graph, Review, SearchResult, Status } from './types';

const navigation = [
  { id: 'workspace', label: 'Workspace', icon: Columns2 },
  { id: 'graph', label: 'Graph explorer', icon: Network },
  { id: 'search', label: 'Search', icon: Search },
  { id: 'review', label: 'Review queue', icon: ClipboardList },
] as const;

export default function App() {
  const [dark, setDark] = useState(() => {
    try { return (localStorage.getItem('pole-theme') ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark'; }
    catch { return false; }
  });
  const [view, setView] = useState<View>('workspace');
  const [status, setStatus] = useState<Status | null>(null);
  const [graph, setGraph] = useState<Graph>({ nodes: [], edges: [] });
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [source, setSource] = useState<Citation | null>(null);
  const [upload, setUpload] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const [queryError, setQueryError] = useState('');
  const [searching, setSearching] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const result: SearchResult | null = turns.at(-1)?.result ?? null;

  const refresh = useCallback(async () => {
    const [nextStatus, nextGraph, nextReviews] = await Promise.all([api.status(), api.graph(), api.reviews()]);
    setStatus(nextStatus); setGraph(nextGraph); setReviews(nextReviews); setConnectionError('');
  }, []);

  useEffect(() => {
    const update = () => void refresh().catch((error) => setConnectionError(errorMessage(error)));
    update();
    const timer = window.setInterval(update, 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (status?.total_documents === 0) {
      setTurns([]); setSource(null); setSelected(null); setQueryError('');
    }
  }, [status?.total_documents]);

  async function search(question: string, selectedId?: string) {
    setQueryError(''); setSearching(true); setSelected(null);
    try {
      const lastGrounded = [...turns].reverse().find(turn => turn.result.citations.length)?.result;
      const previousCases = [...new Set(lastGrounded?.citations.map(source => source.fir_number))].slice(0, 50);
      const reply = await api.query(question, turns.slice(-80).map(turn => turn.question),
        result?.pending_question, selectedId, result?.person_id, previousCases);
      setTurns(previous => [...previous, { question, result: reply }]);
    }
    catch (error) { setQueryError(errorMessage(error)); }
    finally { setSearching(false); }
  }

  const showGraph = view === 'graph' || view === 'workspace';
  const showSearch = view === 'search' || view === 'workspace';
  return <div className="app-shell" data-theme={dark ? "dark" : "light"}>
    <aside className="sidebar"><Brand />
    <nav className="navigation" aria-label="Workspace views">
      {navigation.map(({ id, label, icon: Icon }) => <button key={id} aria-current={view === id ? 'page' : undefined} onClick={() => setView(id)}>
        <Icon size={16} /> {label}
        {id === 'review' && status && status.pending_reviews > 0 && <span className="count">{status.pending_reviews}</span>}
      </button>)}

    </nav>
    <button className="theme-switch" onClick={() => {
      setDark(!dark); try { localStorage.setItem('pole-theme', dark ? 'light' : 'dark'); } catch {}
    }}>{dark ? <Sun size={16} /> : <Moon size={16} />}{dark ? 'Light appearance' : 'Dark appearance'}</button>
    <StorageStatus status={status} /></aside>
    <div className="work-area">
    <Navbar title={view === 'workspace' ? 'Investigation workspace' : navigation.find(item => item.id === view)!.label} onUpload={() => setUpload(true)} />
    {view === 'workspace' && <dl className="workspace-summary">{[
      ['Indexed records', status?.total_documents], ['Entities', status?.total_nodes],
      ['Relationships', status ? graph.edges.length : undefined], ['Cross-case links', status?.cross_case_links],
    ].map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value ?? '–'}</dd></div>)}</dl>}
    {connectionError && <div className="connection-error" role="alert"><CircleAlert size={16} />{connectionError}<button className="button subtle" onClick={() => void refresh().catch((error) => setConnectionError(errorMessage(error)))}>Retry</button></div>}
    <main className={'workspace view-' + view + (source ? ' with-source' : '')}>
      {showSearch && <SearchChatPanel search={(question, id) => void search(question, id)} turns={turns} reset={() => {
        setTurns([]); setQueryError(''); setSelected(null);
      }} busy={searching} error={queryError} onSource={setSource} />}
      {showGraph && <GraphExplorer overview={view === 'workspace'} graph={graph} selected={selected} setSelected={setSelected} matches={result?.matched_subgraph ?? null} onSource={setSource} />}
      {view === 'review' && <HitlReviewPanel reviews={reviews} refresh={refresh} onSource={setSource} />}
      {source && <SourceViewerDrawer citation={source} close={() => setSource(null)} />}
    </main></div>
    {upload && <PdfUploadModal close={() => setUpload(false)} complete={refresh} focus={(id) => {
      setUpload(false); setView('workspace'); setSelected(id);
    }} />}
  </div>;
}

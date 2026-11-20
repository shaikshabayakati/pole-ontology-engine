import { Database, Download, Layers3, Upload } from 'lucide-react';
import { sampleURL } from '../api/client';
import type { Status } from '../types';

export type View = 'workspace' | 'graph' | 'search' | 'review';

export function Brand() {
  return <div className="brand"><Layers3 size={30} strokeWidth={1.8} />
    <div><strong>POLE+O</strong><small>Police Ontology Engine</small></div>
  </div>;
}

export function StorageStatus({ status }: { status: Status | null }) {
  const labels: Record<string, string> = {
    neo4j: 'Neo4j AuraDB', sqlite: 'Local database', unavailable: 'Database unavailable', memory: 'Session memory',
  };
  return <div className="storage-status" title={status?.reason || status?.database || undefined}>
    <Database size={18} /><div><small>Data source</small><strong>
      {status ? labels[status.storage] ?? status.storage : 'Connecting…'}
    </strong></div>
  </div>;
}

export default function Navbar({ title, onUpload }: { title: string; onUpload: () => void }) {
  return <header className="command"><h1>{title}</h1>
    <div className="command-actions">
      <a className="button subtle" href={sampleURL}><Download size={16} /> Sample PDF</a>
      <button className="button primary" onClick={onUpload}><Upload size={16} /> Upload document</button>
    </div>
  </header>;
}

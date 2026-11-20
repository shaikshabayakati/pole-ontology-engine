import { Check, ClipboardList, FileText, X } from 'lucide-react';
import { useState } from 'react';
import { api, errorMessage } from '../api/client';
import type { Citation, Entity, Review } from '../types';

function Candidate({ label, entity, onSource }: { label: string; entity: Entity; onSource: (citation: Citation) => void }) {
  return <div className="candidate"><small>{label}</small><h3>{entity.name}</h3>
    <dl>{Object.entries(entity.properties).filter(([, value]) => value.length).map(([key, value]) => <div key={key}>
      <dt>{key.replaceAll('_', ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') : value}</dd>
    </div>)}</dl>
    <div className="entity-sources">{entity.sources.map((source, index) => <button key={index} className="citation" onClick={() => onSource(source)}><FileText size={13} />{source.fir_number} · Pg {source.page_number}</button>)}</div>
  </div>;
}

export default function HitlReviewPanel({ reviews, refresh, onSource }: {
  reviews: Review[]; refresh: () => Promise<void>; onSource: (citation: Citation) => void;
}) {
  const [active, setActive] = useState('');
  const [error, setError] = useState('');
  const [history, setHistory] = useState(false);
  const pending = reviews.filter((review) => review.status === 'PENDING');

  async function decide(id: string, decision: 'approve' | 'reject') {
    setActive(id); setError('');
    try { await api.decide(id, decision); await refresh(); }
    catch (failure) { setError(errorMessage(failure)); }
    finally { setActive(''); }
  }

  return <section className="panel review-panel">
    <div className="panel-title"><span className="section-icon"><ClipboardList size={17} /></span><div><h2>Entity resolution</h2><p>{pending.length} pending {pending.length === 1 ? 'review' : 'reviews'}</p></div></div>
    <div className="review-body">
      <div className="review-tabs"><button aria-pressed={!history} onClick={() => setHistory(false)}>Pending</button><button aria-pressed={history} onClick={() => setHistory(true)}>Decision history</button></div>
      {error && <p className="error" role="alert">{error}</p>}
      {(history ? reviews.filter((review) => review.status !== 'PENDING') : pending).map((review) => <article className="review-card" key={review.review_id}>
        <div className="review-header"><h3>{review.entity_type} match</h3><span>{Math.round(review.confidence_score * 100)}% match</span>{history && <span>{review.status}</span>}</div>
        <p className="rationale">{review.match_rationale}</p>
        <div className="review-candidates"><Candidate label="Incoming record" entity={review.source_entity} onSource={onSource} /><Candidate label="Existing entity" entity={review.target_entity} onSource={onSource} /></div>
        {!history && <div className="review-actions">
          <button className="button subtle" disabled={!!active} onClick={() => void decide(review.review_id, 'reject')}><X size={16} /> Reject</button>
          <button className="button primary" disabled={!!active} onClick={() => void decide(review.review_id, 'approve')}><Check size={16} /> Approve &amp; merge</button>
        </div>}
      </article>)}
      {!history && !pending.length && <p className="empty-review">No matches are awaiting review.</p>}
      {history && !reviews.some((review) => review.status !== 'PENDING') && <p className="empty-review">No review decisions yet.</p>}
    </div>
  </section>;
}

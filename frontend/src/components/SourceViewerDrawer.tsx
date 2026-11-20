import { FileText, Fingerprint, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '../api/client';
import type { Citation, RecordDocument } from '../types';

export default function SourceViewerDrawer({ citation, close }: { citation: Citation; close: () => void }) {
  const [record, setRecord] = useState<RecordDocument | null>(null);
  const [error, setError] = useState('');
  const highlight = useRef<HTMLDivElement>(null);

  const closeRef = useRef(close);
  closeRef.current = close;
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    closeButton.current?.focus({ preventScroll: true });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('dialog[open]')) closeRef.current();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setRecord(null);
    api.document(citation.doc_id, controller.signal).then(setRecord).catch((error) => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [citation.doc_id]);

  useEffect(() => { highlight.current?.scrollIntoView({ block: 'nearest' }); }, [record, citation]);

  return <aside className="panel source-drawer" aria-label="Source inspector">
    <div className="panel-title"><span className="section-icon"><FileText size={17} /></span><div><h2>Source inspector</h2><p>{citation.fir_number}</p></div>
      <button ref={closeButton} className="icon-button close-button" onClick={close} aria-label="Close source inspector"><X size={19} /></button>
    </div>
    <div className="source-body">
      <div className="source-quote"><strong>Page {citation.page_number} · Lines {citation.line_start}–{citation.line_end}</strong><blockquote>{citation.verbatim_quote}</blockquote></div>
      {error && <p className="error" role="alert">{error}</p>}
      {!record && !error && <p className="progress-text">Loading source…</p>}
      {record && <>
        <div className="document-meta"><strong>{record.file_name}</strong><span>{[record.document_type, record.police_station, record.demo ? 'Synthetic' : ''].filter(Boolean).join(' · ')}</span></div>
        {record.pages.map((lines, p) => <section key={p} className="document-page"><h3>Page {p + 1}</h3>
          {lines.map((line, n) => {
            const active = p + 1 === citation.page_number && n + 1 >= citation.line_start && n + 1 <= citation.line_end;
            return <div key={n} ref={active && n + 1 === citation.line_start ? highlight : undefined} className={active ? 'line highlighted' : 'line'}>
              <span>{n + 1}</span><div>{line || ' '}</div>
            </div>;
          })}
        </section>)}
        <div className="fingerprint"><Fingerprint size={16} /><div><strong>SHA-256</strong><code>{record.file_hash_sha256}</code></div></div>
      </>}
    </div>
  </aside>;
}

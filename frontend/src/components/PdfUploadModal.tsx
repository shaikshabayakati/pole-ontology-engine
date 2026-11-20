import { Check, FileUp, UploadCloud, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '../api/client';
import type { UploadResult } from '../types';

const stages = [
  ['parse', 'Read document'], ['normalize', 'Normalize identifiers'], ['embed', 'Generate embeddings'],
  ['extract', 'Extract ontology'], ['resolve', 'Resolve entities'], ['save', 'Save to graph'],
];

export default function PdfUploadModal({ close, complete, focus }: {
  close: () => void; complete: () => Promise<void>; focus: (id: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState('FIR');
  const [station, setStation] = useState('');
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(-1);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => { dialog.current?.showModal(); }, []);

  function select(next?: File) {
    if (!next) return;
    setError(''); setResult(null); setStep(-1);
    if (!/\.(pdf|txt)$/i.test(next.name)) { setError('Choose a PDF or TXT document.'); setFile(null); return; }
    setFile(next);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setStep(0);
    try {
      const id = await api.upload(file, type, station);
      for (;;) {
        const job = await api.job(id);
        setStep(stages.findIndex(([key]) => key === job.stage));
        if (job.status === 'failed') throw new Error(job.error || 'Upload failed.');
        if (job.status === 'complete' && job.result) {
          setResult(job.result); setStep(stages.length); await complete(); return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 350));
      }
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  return <dialog aria-labelledby="upload-heading" ref={dialog} className="upload-dialog" onCancel={(event) => { event.preventDefault(); if (!busy) close(); }}>
    <div className="panel-title"><span className="section-icon"><FileUp size={19} /></span><div><h2 id="upload-heading">Upload case document</h2><p>PDF or UTF-8 text</p></div>
      <button className="icon-button close-button" type="button" disabled={busy} onClick={close} aria-label="Close upload"><X size={20} /></button>
    </div>
    <form className="upload-body" onSubmit={(event) => void submit(event)}>
      {!result && <>
        <button type="button" className={'dropzone' + (drag ? ' dragging' : '')} disabled={busy} onClick={() => filePicker.current?.click()}
          onDragOver={(event) => { event.preventDefault(); if (!busy) setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(event) => { event.preventDefault(); setDrag(false); if (!busy) select(event.dataTransfer.files[0]); }}>
          <UploadCloud size={30} /><strong>{file?.name ?? 'Drop a file or browse'}</strong><span>{file ? Math.ceil(file.size / 1024) + ' KB' : 'PDF or TXT'}</span>
        </button>
        <input ref={filePicker} type="file" accept=".pdf,.txt" hidden onChange={(event) => { select(event.target.files?.[0]); event.target.value = ''; }} />
        <div className="upload-fields">
          <label>Document type<select value={type} disabled={busy} onChange={(event) => setType(event.target.value)}><option>FIR</option><option>Case Diary</option><option>Chargesheet</option><option>Other</option></select></label>
          <label>Police station<input value={station} disabled={busy} maxLength={160} onChange={(event) => setStation(event.target.value)} placeholder="Optional" /></label>
        </div>
      </>}
      {step >= 0 && <ol className="upload-progress" aria-label="Ingestion progress">{stages.map(([key, label], index) => <li key={key} className={index <= step ? 'stage-active' : ''}>
        {index < step ? <Check size={14} /> : index === step && busy ? <span className="spinner" /> : <i />}{label}
      </li>)}</ol>}
      {error && <p className="error" role="alert">{error}</p>}
      {result && <div className="upload-result"><h3>{result.fir_number} {result.duplicate ? 'already indexed' : 'indexed'}</h3>
        <div><span><strong>{result.nodes_extracted}</strong> Entities</span><span><strong>{result.edges_extracted}</strong> Relationships</span><span><strong>{result.cross_case_links_found}</strong> Cross-case links</span><span><strong>{result.hitl_flagged}</strong> Reviews flagged</span></div>
      </div>}
      <div className="review-actions"><button type="button" className="button subtle" disabled={busy} onClick={close}>{result ? 'Done' : 'Cancel'}</button>
        {result?.case_id && <button type="button" className="button primary" onClick={() => focus(result.case_id!)}>Focus case on graph</button>}
        {!result && <button type="submit" className="button primary" disabled={!file || busy}><FileUp size={16} /> {busy ? 'Processing…' : 'Upload & index'}</button>}
      </div>
    </form>
  </dialog>;
}

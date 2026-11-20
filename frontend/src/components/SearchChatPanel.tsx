import { ArrowUp, ArrowUpRight, ChevronDown, FileText, MessagesSquare, Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ChatTurn, Citation } from '../types';

const examples = [
  'Which cases involve AP02AB1234?',
  'How are FIR-104/2025 and FIR-042/2026 connected?',
  'Who is mentioned in the NH-44 Night Riders Gang record?',
];

export default function SearchChatPanel({ search, turns, reset, busy, error, onSource }: {
  search: (question: string, id?: string) => void; turns: ChatTurn[]; reset: () => void; busy: boolean;
  error: string; onSource: (citation: Citation) => void;
}) {
  const [input, setInput] = useState('');
  const result = turns.at(-1)?.result;
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { if (turns.length) bottom.current?.scrollIntoView({ block: 'nearest' }); }, [turns]);
  function submit(question: string) {
    if (question.trim().length >= 1 && !busy) {
      setInput('');
      search(question.trim());
    }
  }
  return <section className="panel search-panel" aria-label="GraphRAG search">
    <div className="panel-title"><MessagesSquare size={18} /><h2>Case assistant</h2>
      {!!turns.length && <button className="button subtle fit" disabled={busy} onClick={() => {reset(); setInput('');}}>New chat</button>}</div>
    <div className="search-body">
      {!result && !busy && <div className="search-empty">
        <Search size={26} strokeWidth={1.5} className="search-mark" />
        <h3>Ask the records</h3>
        <p>Find a person, trace a vehicle, or follow a connection back to its source.</p>
      </div>}
      {busy && <p className="progress-text" role="status"><span className="spinner" /> Searching records and relationships…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {turns.map(({ question, result }, turnIndex) => <div key={turnIndex} className="answer chat-turn">
        <p className="chat-question">{question}</p>
        {result.answer.split(/\n{2,}/).map((line, index) => <p key={index}>
          {line.split(/(\[\d+\])/).map((part, i) => {
            const reference = /^\[(\d+)\]$/.exec(part);
            const source = reference ? result.citations[Number(reference[1]) - 1] : undefined;
            return source ? <button key={i} className="citation" onClick={() => onSource(source)}>
              <FileText size={12} /> {source.fir_number} · Pg {source.page_number}
            </button> : part;
          })}
        </p>)}
        {result.candidates?.map(candidate => <button key={candidate.id} className="person-candidate"
          disabled={busy || turnIndex !== turns.length - 1}
          onClick={() => search('Confirm ' + candidate.name, candidate.id)}>
          <strong>{candidate.name}</strong><small>{candidate.score}/100 similarity</small>
          <span>{[...candidate.stations, ...candidate.cases].join(' · ')}</span>
          {!!candidate.reasons.length && <span>Matched {candidate.reasons.join(', ')}</span>}
        </button>)}
        {!result.pending_question && <details className="telemetry">
          <summary>Retrieval details <ChevronDown size={15} /></summary>
          <h4>Graph traversal</h4>
          <pre>{result.cypher_executed ?? 'In-memory traversal · ' + result.matched_subgraph.edges.length + ' relationships'}</pre>
          <h4>Hybrid passage matches</h4>
          {result.top_k_chunks.map((chunk) => <button className="chunk" key={chunk.chunk_id} onClick={() => onSource(chunk)}>
            <strong>{chunk.fir_number} · Pg {chunk.page_number}</strong><span>{chunk.cosine != null ? "Cosine " + chunk.cosine.toFixed(2) : "Lexical"}</span><small>{chunk.text}</small>
          </button>)}
          {!result.top_k_chunks.length && <p>No vector matches.</p>}
        </details>}
      </div>)}
      <div ref={bottom} />
      {!result && <div className="examples"><span>Suggested questions</span>
        {examples.map((example) => <button key={example} disabled={busy} onClick={() => submit(example)}>{example}<ArrowUpRight size={14} /></button>)}
      </div>}
    </div>
    <form className="search-form" onSubmit={(event) => { event.preventDefault(); submit(input); }}>
      <label className="sr-only" htmlFor="question">Search case records</label>
      <textarea id="question" value={input} rows={2} maxLength={1000} placeholder="Ask about the case records…" onChange={(event) => setInput(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(input); } }} />
      <button className="button primary icon-button" type="submit" aria-label="Search" disabled={busy || !input.trim()}><ArrowUp size={18} /></button>
    </form>
  </section>;
}

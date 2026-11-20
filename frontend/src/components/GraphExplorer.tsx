import { Background, BackgroundVariant, Controls, Handle, MarkerType, Position, ReactFlow, useReactFlow, type Node, type NodeProps } from '@xyflow/react';
import { Building2, CarFront, Clock3, FolderOpen, Landmark, MapPin, Scale, ScanLine, SlidersHorizontal, UserRound, Fingerprint, GitBranch, LocateFixed, Network, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, errorMessage } from '../api/client';
import { entityTypes, type Citation, type Entity, type EntityType, type Graph } from '../types';

const colors: Record<EntityType, string> = {
  Person: '#eaa5b3', Case: '#e7c27e', Crime: '#c8aeef', Location: '#92c7b0',
  Vehicle: '#f6b75d', Organisation: '#ed8fc3', Evidence: '#6dd9e5',
  PoliceStation: '#8eabce', OffenceSection: '#c9a985', TimeWindow: '#a3b7bd',
};
const columns: EntityType[][] = [
  ['PoliceStation', 'OffenceSection'], ['Case'], ['Person', 'Evidence'],
  ['Vehicle', 'Crime', 'Organisation'], ['Location', 'TimeWindow'],
];

const glyphs = { Case: FolderOpen, Person: UserRound, Crime: ScanLine, Location: MapPin,
  Vehicle: CarFront, Organisation: Building2, Evidence: Fingerprint, PoliceStation: Landmark,
  OffenceSection: Scale, TimeWindow: Clock3 };
type DiagramNode = Node<{ entity: Entity; faded: boolean; focused: boolean; anchor: boolean }, 'entity'>;

function EntityNode({ data }: NodeProps<DiagramNode>) {
  const { entity, focused, faded } = data;
  const Glyph = glyphs[entity.type];
  return <div className={'entity-node ' + (focused ? 'entity-focused ' : '') + (faded ? 'entity-faded ' : '') + (data.anchor ? 'entity-anchor' : '')} style={{ '--entity-color': colors[entity.type] } as React.CSSProperties}>
    <Handle type="target" position={Position.Left} />
    <span className="node-glyph"><Glyph size={23} strokeWidth={1.6} /></span>
    <small>{entity.type.replace(/([a-z])([A-Z])/g, '$1 $2')}</small>
    <strong title={entity.name}>{entity.name}</strong>
    <Handle type="source" position={Position.Right} />
  </div>;
}
const nodeTypes = { entity: EntityNode };

function Recenter({ revision }: { revision: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const timer = window.setTimeout(() => { void fitView({ padding: 0.12, duration: 260, maxZoom: 1 }); }, 90);
    return () => window.clearTimeout(timer);
  }, [revision, fitView]);
  return null;
}

export default function GraphExplorer({ overview, graph, selected, setSelected, matches, onSource }: {
  overview: boolean; graph: Graph; selected: string | null; setSelected: (id: string | null) => void;
  matches: Graph | null; onSource: (source: Citation) => void;
}) {
  const canvas = useRef<HTMLDivElement>(null);
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setCompact(entry.contentRect.width < 500));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const [scope, setScope] = useState<string | null>(null);
  const [pathOpen, setPathOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const cases = graph.nodes.filter(node => node.type === 'Case');
  const caseId = scope ?? (overview ? cases[0]?.id : '');
  const activeCase = cases.find(node => node.id === caseId);
  const [filters, setFilters] = useState<EntityType[]>([]);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [path, setPath] = useState<Graph | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const entity = graph.nodes.find((node) => node.id === selected);
  const activePath = path && path.nodes.every((node) => graph.nodes.some((current) => current.id === node.id)) ? path : null;
  useEffect(() => {
    if (selected && activeCase && entity && !entity.sources.some(s => s.fir_number === activeCase.name)) setScope('');
  }, [activeCase, entity, selected]);
  useEffect(() => { if (matches?.nodes.length) setScope(''); }, [matches]);
  const available = entityTypes.filter((type) => graph.nodes.some((node) => node.type === type));

  const diagram = useMemo(() => {
    const focused = new Set((activePath ?? matches)?.nodes.map((node) => node.id));
    const focusEdges = new Set((activePath ?? matches)?.edges.map((edge) => edge.id));
    if (selected && !activePath) {
      focused.clear();
      focusEdges.clear();
      focused.add(selected);
      graph.edges.forEach((edge) => {
        if ([edge.source, edge.target].includes(selected)) {
          focused.add(edge.source); focused.add(edge.target); focusEdges.add(edge.id);
        }
      });
    }
    const scoped = graph.nodes.filter(node => !activeCase || node.id === activeCase.id ||
      node.sources.some(source => source.fir_number === activeCase.name));
    const show = scoped.filter(node => !filters.length || filters.includes(node.type));
    const orbit = show.filter(node => node.id !== activeCase?.id);
    const nodes: DiagramNode[] = show.map(node => {
      const column = columns.findIndex(types => types.includes(node.type));
      const group = show.filter(n => columns[column].includes(n.type));
      let position = { x: column * 200, y: (group.indexOf(node) - (group.length - 1) / 2) * 110 };
      if (activeCase) {
        const angle = (orbit.indexOf(node) / Math.max(1, orbit.length)) * Math.PI * 2 - Math.PI / 2;
        const factor = Math.max(1, orbit.length / 9);
        position = node.id === activeCase.id ? { x: 0, y: 0 } :
          { x: Math.cos(angle) * (compact ? 139 : 255) * factor, y: Math.sin(angle) * (compact ? 212 : 177) * factor };
      }
      return { id: node.id, type: 'entity', position,
        data: { entity: node, anchor: node.id === activeCase?.id, focused: focused.has(node.id),
          faded: focused.size > 0 && !focused.has(node.id) } };
    });
    const visible = new Set(nodes.map((node) => node.id));
    const edges = graph.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target) && (!activeCase || edge.citation.fir_number === activeCase.name)).map((edge) => {
      const active = focusEdges.has(edge.id);
      const color = active ? '#f0bd72' : '#89968f';
      return {
        id: edge.id, source: edge.source, target: edge.target, type: activeCase ? 'straight' : 'default',
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
        style: { stroke: color, strokeWidth: active ? 2.2 : 1.65, opacity: focusEdges.size && !active ? 0.17 : 0.77 },
        label: activePath && active ? edge.type.replaceAll('_', ' ').toLowerCase() : undefined,
        labelStyle: { fill: '#c6d9f3', fontSize: 10 },
        labelBgStyle: { fill: '#111b28' },
      };
    });
    return { nodes, edges };
  }, [graph, filters, selected, activePath, matches, activeCase, compact]);

  async function findPath() {
    setError(''); setPath(null); setLoading(true);
    try {
      setPath(await api.path(from, to)); setScope('');
      setSelected(null); setFilters([]); setRevision((value) => value + 1);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setLoading(false); }
  }

  return <section className="panel graph-panel" aria-label="Ontology graph">
    <div className="panel-title graph-heading"><Network size={18} /><h2>Relationship graph</h2>
      <button className="icon-button fit" title="Fit graph to view" aria-label="Fit graph to view" onClick={() => setRevision(value => value + 1)}><LocateFixed size={17} /></button>
    </div>
    <div className="graph-toolbar"><label className="case-select"><FolderOpen size={15} />
      <select aria-label="Graph case" value={caseId ?? ''} onChange={event => {setScope(event.target.value); setPath(null); setSelected(null); setFilters([]);}}>
        <option value="">All records</option>{cases.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
      <button className="tool-toggle" aria-expanded={filterOpen} onClick={() => setFilterOpen(!filterOpen)}><SlidersHorizontal size={15} /> Filters{filters.length ? ' (' + filters.length + ')' : ''}</button>
      <button className="tool-toggle" aria-expanded={pathOpen} onClick={() => setPathOpen(!pathOpen)}><GitBranch size={15} /> Find path</button>
    </div>
    {pathOpen && <div className="pathbar">
      <GitBranch size={16} />
      <select aria-label="Entity A" value={from} onChange={(event) => setFrom(event.target.value)}><option value="">Entity A</option>{graph.nodes.map((node) => <option key={node.id} value={node.id}>{node.name}</option>)}</select>
      <span>→</span>
      <select aria-label="Entity B" value={to} onChange={(event) => setTo(event.target.value)}><option value="">Entity B</option>{graph.nodes.map((node) => <option key={node.id} value={node.id}>{node.name}</option>)}</select>
      <button className="button subtle" disabled={!from || !to || loading} onClick={() => void findPath()}>{loading ? 'Finding…' : 'Find path'}</button>
      {activePath && <button className="icon-button" aria-label="Clear path" onClick={() => setPath(null)}><X size={16} /></button>}
    </div>}
    {error && <p className="path-message error" role="alert">{error}</p>}
    {activePath && <p className="path-message">{activePath.nodes.map((node) => node.name).join(' → ')}</p>}
    <div ref={canvas} className={compact ? "graph-canvas compact" : "graph-canvas"}>
      <ReactFlow nodes={diagram.nodes} edges={diagram.edges} nodeTypes={nodeTypes} nodesDraggable={false} nodesConnectable={false}
        minZoom={0.18} maxZoom={2.4} fitView
        onPaneClick={() => setSelected(null)}
        onNodeClick={(_, node) => {
          setPath(null); setSelected(node.id);
          if (node.data.entity.sources[0]) onSource(node.data.entity.sources[0]);
        }}
        onEdgeClick={(_, edge) => {
          const relation = graph.edges.find((item) => item.id === edge.id);
          if (relation) onSource(relation.citation);
        }}>
        <Background variant={BackgroundVariant.Dots} color="#37403e" gap={19} size={0.9} />
        <Controls position="bottom-left" showInteractive={false} />
        <Recenter revision={revision + ':' + compact + ':' + diagram.nodes.map((node) => node.id).join(',')} />
      </ReactFlow>
      {!diagram.nodes.length && <div className="canvas-empty">Upload a record to populate the graph.</div>}
    </div>
    {entity && <div className="entity-inspector">
      <div><small>{entity.type}</small><h3>{entity.name}</h3></div>
      <div className="entity-details">{Object.entries(entity.properties).map(([key, value]) => <span key={key}><small>{key.replaceAll('_', ' ')}</small> {Array.isArray(value) ? value.join(', ') : value}</span>)}</div>
      <div className="entity-sources">{entity.sources.map((source, index) => <button className="citation" key={index} onClick={() => onSource(source)}><Fingerprint size={13} /> {source.fir_number} · Pg {source.page_number}</button>)}</div>
      <button className="icon-button close-button" aria-label="Close entity details" onClick={() => setSelected(null)}><X size={16} /></button>
    </div>}
    {filterOpen && <div className="legend" aria-label="Entity type filters">
      {available.map((type) => <button key={type} aria-pressed={!filters.length || filters.includes(type)} onClick={() =>
        setFilters((values) => values.includes(type) ? values.filter((value) => value !== type) : [...values, type])}>
        <i style={{ background: colors[type] }} />{type.replace(/([a-z])([A-Z])/g, '$1 $2')}
      </button>)}
      {filters.length > 0 && <button className="clear" onClick={() => setFilters([])}>Clear filters</button>}
    </div>}
    <div className="graph-caption"><span><i />{activeCase ? activeCase.name : 'All records'}</span>
      <span>{diagram.nodes.length} entities · {diagram.edges.length} relationships</span></div>
  </section>;
}

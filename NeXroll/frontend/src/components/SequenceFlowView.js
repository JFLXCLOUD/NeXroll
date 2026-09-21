import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Panel,
  MarkerType,
  BackgroundVariant,
  Controls,
  MiniMap,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  useNodesState,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Play, Clapperboard, GitBranch, Plus, SkipForward, LayoutGrid, ArrowLeft, ArrowRight } from 'lucide-react';
import { hasCondition, describeCondition, describeOtherwise, needsPlaybackInfo } from '../utils/sequenceConditions';

/**
 * SequenceFlowView - the Sequence Builder's Flow view: the same sequence drawn
 * as a node workflow (in the style of n8n) instead of a list.
 *
 * Block flow_positions store canvas placement independently of playback order.
 * The initial layout runs left to right from playback to movie:
 *   - drag nodes freely; use the order controls to change playback order
 *   - the + on a connection inserts a block at that point
 *   - in Advanced mode a conditional block is drawn as an IF node that
 *     branches to the block (condition met) and to its alternative or a
 *     Skip (not met), both joining the next step
 * Selecting any node selects its block for the Block settings panel.
 */

const NODE_W = 260;
const IF_W = 220;
const START_W = 220;
const GAP = 100;
const BRANCH_Y = 96;
// Fitting a long sequence must not shrink it past reading size; pan instead.
const FIT = { padding: 0.12, minZoom: 0.8, maxZoom: 1.05 };
const EDGE_PAD = 28;

export const INSERTABLE_BLOCKS = [
  { type: 'random', code: 'CAT', label: 'Category' },
  { type: 'fixed', code: 'FIX', label: 'Fixed preroll' },
  { type: 'nexup_trailers', code: 'TRL', label: 'NeX-Up trailers' },
  { type: 'library_trailers', code: 'LIB', label: 'Library trailers' },
  { type: 'dynamic_preroll', code: 'GEN', label: 'Generated preroll' },
];

const BLOCK_CODES = {
  random: 'CAT', sequential: 'CAT', fixed: 'FIX', nexup_trailers: 'TRL', library_trailers: 'LIB',
  dynamic_preroll: 'GEN', coming_soon_list: 'GEN', separator: 'II',
};

// ---- Nodes -------------------------------------------------------------

const TerminalNode = ({ data }) => (
  <div className={`nx-flow-terminal ${data.kind}`}>
    {data.kind === 'end' && <Handle type="target" position={Position.Left} />}
    <span className="icon">{data.kind === 'start' ? <Play size={15} /> : <Clapperboard size={15} />}</span>
    <span className="copy"><strong>{data.title}</strong><small>{data.subtitle}</small></span>
    {data.kind === 'start' && <Handle type="source" position={Position.Right} />}
  </div>
);

const BlockNode = ({ data, selected }) => (
  <div className={`nx-flow-node${selected || data.active ? ' selected' : ''}${data.branch ? ` branch ${data.branch}` : ''}`}>
    <Handle type="target" position={Position.Left} />
    <i>{data.code}</i>
    <span className="copy">
      <strong title={data.title}>{data.title}</strong>
      <small title={data.description}>{data.description}</small>
      {data.badge && <em className="nx-draft-badge violet"><GitBranch size={10} /> {data.badge}</em>}
    </span>
    {data.order != null && <span className="order">{data.order}</span>}
    <Handle type="source" position={Position.Right} />
  </div>
);

const SkipNode = ({ data }) => (
  <div className={`nx-flow-skip${data.active ? ' selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <SkipForward size={13} /> Skip
    <Handle type="source" position={Position.Right} />
  </div>
);

const IfNode = ({ data, selected }) => (
  <div className={`nx-flow-if${selected || data.active ? ' selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <i><GitBranch size={14} /></i>
    <span className="copy">
      <strong>IF{data.pluginOnly && <em className="nx-flow-tag">Jellyfin &amp; Emby</em>}</strong>
      <small title={data.summary}>{data.summary}</small>
    </span>
    <span className="order">{data.order}</span>
    <Handle type="source" id="true" position={Position.Right} style={{ top: '30%' }} />
    <Handle type="source" id="false" position={Position.Right} style={{ top: '72%' }} />
    <span className="nx-flow-if-label true">true</span>
    <span className="nx-flow-if-label false">false</span>
  </div>
);

const nodeTypes = { terminal: TerminalNode, block: BlockNode, skip: SkipNode, ifnode: IfNode };

// ---- Edges -------------------------------------------------------------

// A connection that can carry a "+" to insert a block where it sits.
const InsertEdge = ({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, data }) => {
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const insertAt = data?.insertAt;
  return (
    <>
      <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />
      {insertAt != null && (
        <EdgeLabelRenderer>
          <div className="nx-flow-edge-tools nodrag nopan" style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>
            <button
              type="button"
              className="nx-flow-plus"
              aria-label={`Insert a block at position ${insertAt + 1}`}
              aria-expanded={Boolean(data.menuOpen)}
              aria-haspopup="menu"
              title="Insert a block here"
              onClick={event => { event.stopPropagation(); data.onOpenInsert(data.menuOpen ? null : insertAt); }}
            >
              <Plus size={12} />
            </button>
            {data.menuOpen && (
              <div className="nx-flow-insert-menu" role="menu">
                {INSERTABLE_BLOCKS.map(item => (
                  <button type="button" role="menuitem" key={item.type} onClick={event => { event.stopPropagation(); data.onInsert(item.type, insertAt); }}>
                    <i>{item.code}</i>{item.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

const edgeTypes = { insert: InsertEdge };

// ---- Layout ------------------------------------------------------------

export const layoutSequence = ({ blocks, advanced, selectedIndex, blockTitle, blockDescription, getCategoryName }) => {
  const nodes = [];
  const edges = [];
  let x = 0;
  // The step(s) the next node connects from, and the "+" position they carry.
  let tails = [{ id: 'start', handle: undefined }];

  const connect = (targetId, insertAt) => {
    tails.forEach((tail, i) => {
      edges.push({
        id: `e-${tail.id}-${tail.handle || 'out'}-${targetId}`,
        source: tail.id,
        sourceHandle: tail.handle,
        target: targetId,
        type: 'insert',
        // One "+" per gap: only the first incoming line carries it.
        data: { insertAt: i === 0 ? insertAt : null },
      });
    });
  };

  nodes.push({ id: 'start', type: 'terminal', position: { x, y: 0 }, draggable: false, selectable: false,
    data: { kind: 'start', title: 'Playback starts', subtitle: 'A movie is chosen' } });
  x += START_W + GAP;

  blocks.forEach((block, index) => {
    const active = index === selectedIndex;
    const blockData = {
      index,
      code: BLOCK_CODES[block.type] || 'BLK',
      title: blockTitle(block),
      description: blockDescription(block),
      active,
    };

    if (advanced && hasCondition(block)) {
      const ifId = `if-${index}`;
      nodes.push({ id: ifId, type: 'ifnode', position: { x, y: 0 },
        data: { index, order: index + 1, summary: describeCondition(block.condition), active,
                pluginOnly: needsPlaybackInfo(block.condition) } });
      connect(ifId, index);
      x += IF_W + GAP;

      const trueId = `b-${index}`;
      nodes.push({ id: trueId, type: 'block', position: { x, y: -BRANCH_Y }, draggable: false,
        data: { ...blockData, branch: 'met' } });
      edges.push({ id: `e-${ifId}-true`, source: ifId, sourceHandle: 'true', target: trueId, type: 'insert', data: {}, className: 'nx-flow-edge-true' });

      const falseId = `o-${index}`;
      if (block.otherwise) {
        nodes.push({ id: falseId, type: 'block', position: { x, y: BRANCH_Y }, draggable: false,
          data: { index, code: BLOCK_CODES[block.otherwise.type] || 'BLK', title: 'Otherwise',
                  description: describeOtherwise(block.otherwise, getCategoryName), branch: 'otherwise', active } });
      } else {
        nodes.push({ id: falseId, type: 'skip', position: { x: x + 60, y: BRANCH_Y + 14 }, draggable: false,
          data: { index, active } });
      }
      edges.push({ id: `e-${ifId}-false`, source: ifId, sourceHandle: 'false', target: falseId, type: 'insert', data: {}, className: 'nx-flow-edge-false' });

      x += NODE_W + GAP;
      tails = [{ id: trueId }, { id: falseId }];
      return;
    }

    const id = `b-${index}`;
    nodes.push({ id, type: 'block', position: { x, y: 0 },
      data: { ...blockData, order: index + 1,
              badge: hasCondition(block) ? (needsPlaybackInfo(block.condition) ? 'Conditional / Jellyfin & Emby' : 'Conditional') : null } });
    connect(id, index);
    x += NODE_W + GAP;
    tails = [{ id }];
  });

  nodes.push({ id: 'end', type: 'terminal', position: { x, y: 0 }, draggable: false, selectable: false,
    data: { kind: 'end', title: 'Movie starts', subtitle: 'After the last block' } });
  connect('end', blocks.length);
  nodes.forEach(node => {
    if (node.data.index == null) return;
    const block = blocks[node.data.index];
    const role = node.id.split('-')[0];
    node.id = `${role}-${block.id || block.ui_id || node.data.index}`;
    node.data.positionKey = `${advanced ? 'advanced' : 'simple'}_${role}`;
    const saved = block.flow_positions?.[node.data.positionKey];
    if (Number.isFinite(saved?.x) && Number.isFinite(saved?.y)) node.position = saved;
    node.draggable = true;
  });
  // Edges are constructed using the original index IDs; resolve to stable block IDs.
  const resolve = id => {
    const match = /^(if|b|o)-(\d+)$/.exec(id);
    if (!match) return id;
    const block = blocks[Number(match[2])];
    return `${match[1]}-${block.id || block.ui_id || match[2]}`;
  };
  edges.forEach(edge => {
    edge.source = resolve(edge.source);
    edge.target = resolve(edge.target);
    edge.markerEnd = { type: MarkerType.ArrowClosed, width: 16, height: 16,
      color: edge.className === 'nx-flow-edge-true' ? '#31c48d' : edge.className === 'nx-flow-edge-false' ? '#f0a64b' : '#89939f' };
  });
  return { nodes, edges };
};

// ---- View --------------------------------------------------------------

const FlowCanvas = ({ blocks, advanced, selectedIndex, onSelect, onMove, onInsert, onPositionsChange, blockTitle, blockDescription, getCategoryName, darkMode }) => {
  const [insertOpen, setInsertOpen] = useState(null);
  const { fitView, setViewport } = useReactFlow();
  const wrapperRef = useRef(null);

  // The page re-renders often (its clock ticks) and hands down fresh label
  // functions each time. Re-laying out on every render would snap a node back
  // mid-drag, so the layout only changes when what it draws changes.
  const labels = blocks.map(block => [
    blockTitle(block),
    blockDescription(block),
    block.otherwise ? describeOtherwise(block.otherwise, getCategoryName) : '',
  ]);
  const layoutKey = JSON.stringify([blocks, labels, advanced, selectedIndex]);
  const layout = useMemo(
    () => layoutSequence({ blocks, advanced, selectedIndex, blockTitle, blockDescription, getCategoryName }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [layoutKey]
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  useEffect(() => {
    setNodes(current => layout.nodes.map(node => {
      const previous = current.find(item => item.id === node.id);
      return previous?.dragging ? { ...node, position: previous.position, dragging: true } : node;
    }));
  }, [layout.nodes, setNodes]);
  useEffect(() => { setInsertOpen(null); }, [blocks.length, advanced]);

  // Frame on opening or switching modes; inserting and editing preserve the viewport.
  // Fit the whole flow when it fits at a readable size. A longer one is not
  // shrunk: like n8n, it opens at the start and continues off to the right.
  useEffect(() => {
    const t = setTimeout(() => {
      const box = wrapperRef.current;
      const end = layout.nodes[layout.nodes.length - 1];
      if (!box || !end) return;
      const contentWidth = end.position.x + START_W;
      if (contentWidth * FIT.minZoom <= box.clientWidth - EDGE_PAD * 2) {
        fitView({ ...FIT, duration: 250 });
      } else {
        setViewport({ x: EDGE_PAD, y: box.clientHeight / 2 - 32 * FIT.minZoom, zoom: FIT.minZoom }, { duration: 250 });
      }
    }, 30);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [advanced, fitView, setViewport]);

  const handleInsert = useCallback((type, at) => { setInsertOpen(null); onInsert(type, at); }, [onInsert]);
  const edges = useMemo(() => layout.edges.map(edge => (
    edge.data.insertAt == null ? edge : {
      ...edge,
      data: { ...edge.data, menuOpen: insertOpen === edge.data.insertAt, onOpenInsert: setInsertOpen, onInsert: handleInsert },
    }
  )), [layout.edges, insertOpen, handleInsert]);

  const onNodeDragStop = useCallback((event, node, draggedNodes) => {
    onPositionsChange((draggedNodes || [node]).filter(item => item.data?.index != null).map(item => ({
      index: item.data.index, key: item.data.positionKey, position: item.position,
    })));
  }, [onPositionsChange]);

  const autoArrange = () => {
    const arranged = layoutSequence({ blocks: blocks.map(({ flow_positions, ...block }) => block),
      advanced, selectedIndex, blockTitle, blockDescription, getCategoryName });
    setNodes(arranged.nodes);
    onPositionsChange(arranged.nodes.filter(node => node.data.index != null).map(node => ({
      index: node.data.index, key: node.data.positionKey, position: node.position,
    })));
    requestAnimationFrame(() => fitView({ ...FIT, duration: 250 }));
  };

  return (
    <div ref={wrapperRef} className="nx-flow-canvas" onKeyDown={event => { if (event.key === 'Escape') setInsertOpen(null); }}>
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onNodeClick={(event, node) => { if (node.data?.index != null) onSelect(node.data.index); }}
      onNodeDragStop={onNodeDragStop}
      onPaneClick={() => setInsertOpen(null)}
      nodesConnectable={false}
      deleteKeyCode={null}
      edgesFocusable={false}
      onNodeDragStart={(event, node) => { setInsertOpen(null); if (node.data?.index != null) onSelect(node.data.index); }}
      colorMode={darkMode ? 'dark' : 'light'}
      minZoom={0.3}
      maxZoom={1.6}
      fitView
      fitViewOptions={FIT}
    >
      <Panel position="top-left" className="nx-flow-toolbar">
        <button type="button" onClick={autoArrange}><LayoutGrid size={14} /> Auto arrange</button>
        <span>Drag to position. Arrows show playback order</span>
      </Panel>
      {blocks.length > 0 && <Panel position="top-right" className="nx-flow-order-tools">
        <span>Step {selectedIndex + 1} of {blocks.length}</span>
        <button type="button" aria-label="Play selected block earlier" title="Play earlier" disabled={selectedIndex <= 0} onClick={() => onMove(selectedIndex, selectedIndex - 1)}><ArrowLeft size={15} /></button>
        <button type="button" aria-label="Play selected block later" title="Play later" disabled={selectedIndex >= blocks.length - 1} onClick={() => onMove(selectedIndex, selectedIndex + 1)}><ArrowRight size={15} /></button>
      </Panel>}
      <Background variant={BackgroundVariant.Dots} gap={18} size={1.3} />
      <Controls showInteractive={false} position="bottom-left" />
      <MiniMap
        pannable
        zoomable
        position="bottom-right"
        className="nx-flow-minimap"
        nodeColor={node => (node.type === 'ifnode' ? '#7667ff' : node.data?.branch === 'otherwise' || node.type === 'skip' ? '#f0a64b' : '#31c48d')}
        maskColor={darkMode ? 'rgba(10,10,12,.55)' : 'rgba(240,241,245,.6)'}
      />
    </ReactFlow>
    </div>
  );
};

const SequenceFlowView = props => (
  <div className="nx-flow" aria-label="Sequence flow">
    <ReactFlowProvider>
      <FlowCanvas {...props} />
    </ReactFlowProvider>
    {props.blocks.length === 0 && (
      <p className="nx-flow-hint">Use the + between Playback starts and Movie starts, to add your first block.</p>
    )}
  </div>
);

export default SequenceFlowView;

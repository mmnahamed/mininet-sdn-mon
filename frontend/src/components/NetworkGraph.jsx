import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

// Role → visual style map
const NODE_STYLE = {
    spine: { fill: '#0f172a', stroke: '#6366f1', glow: '#6366f1', shape: 'rect', size: 18 },
    aggregation: { fill: '#0f172a', stroke: '#3b82f6', glow: '#3b82f6', shape: 'rect', size: 14 },
    leaf: { fill: '#0f172a', stroke: '#06b6d4', glow: '#06b6d4', shape: 'rect', size: 12 },
    switch: { fill: '#1e293b', stroke: '#3b82f6', glow: '#3b82f6', shape: 'rect', size: 13 },
    router: { fill: '#1e293b', stroke: '#f59e0b', glow: '#f59e0b', shape: 'hexagon', size: 16 },
    host: { fill: '#064e3b', stroke: '#10b981', glow: '#10b981', shape: 'circle', size: 10 },
};

const LINK_COLOR = {
    spine: '#818cf8',
    cross_agg: '#f59e0b',
    agg_leaf: '#38bdf8',
    backbone: '#334155',
    edge: '#1e3a2f',
    uplink: '#f59e0b',
    wan: '#64748b',
};
const LINK_WIDTH = {
    spine: 3, cross_agg: 2.5, agg_leaf: 2, backbone: 2, edge: 1, uplink: 1.5, wan: 1,
};
const LINK_DASH = { wan: [6, 4], cross_agg: [4, 2] };

export default function NetworkGraph({ data }) {
    const fgRef = useRef();
    const containerRef = useRef();
    const [dims, setDims] = useState({ w: 800, h: 600 });
    const [hovered, setHovered] = useState(null);

    useEffect(() => {
        const obs = new ResizeObserver(entries => {
            for (const e of entries)
                setDims({ w: e.contentRect.width, h: e.contentRect.height });
        });
        if (containerRef.current) obs.observe(containerRef.current);
        return () => obs.disconnect();
    }, []);

    useEffect(() => {
        if (!fgRef.current || data.nodes.length === 0) return;
        const fg = fgRef.current;
        fg.d3Force('charge').strength(n => {
            if (n.role === 'spine') return -800;
            if (n.role === 'aggregation') return -500;
            if (n.role === 'leaf') return -350;
            return -200;
        });
        fg.d3Force('link').distance(l => {
            if (l.type === 'wan') return 220;
            if (l.type === 'spine') return 160;
            if (l.type === 'agg_leaf') return 120;
            if (l.type === 'edge') return 80;
            return 140;
        });
        setTimeout(() => fg.zoomToFit(500, 80), 700);
    }, [data]);

    const drawNode = (node, ctx, globalScale) => {
        const style = NODE_STYLE[node.role] || NODE_STYLE[node.type] || NODE_STYLE.host;
        const label = node.label || node.name || `Node ${node.id}`;
        const fontSize = Math.max(10 / globalScale, 4);
        const isHovered = hovered && hovered.id === node.id;

        ctx.shadowBlur = isHovered ? 25 : 12;
        ctx.shadowColor = style.glow;
        ctx.strokeStyle = isHovered ? '#ffffff' : style.stroke;
        ctx.fillStyle = style.fill;
        ctx.lineWidth = (isHovered ? 2.5 : 1.5) / globalScale;

        const s = style.size;

        if (style.shape === 'hexagon') {
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                const a = (i * Math.PI) / 3;
                const x = node.x + s * Math.cos(a);
                const y = node.y + s * Math.sin(a);
                i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.fill(); ctx.stroke();
            // router icon
            ctx.beginPath();
            ctx.moveTo(node.x - 5, node.y - 5); ctx.lineTo(node.x + 5, node.y + 5);
            ctx.moveTo(node.x + 5, node.y - 5); ctx.lineTo(node.x - 5, node.y + 5);
            ctx.stroke();
        } else if (style.shape === 'circle') {
            ctx.beginPath();
            ctx.arc(node.x, node.y, s, 0, 2 * Math.PI);
            ctx.fill(); ctx.stroke();
        } else {
            // rect (switches)
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(node.x - s, node.y - s, s * 2, s * 2, 3);
            else ctx.rect(node.x - s, node.y - s, s * 2, s * 2);
            ctx.fill(); ctx.stroke();

            // LED indicators per role
            const ledColor = node.role === 'spine' ? '#818cf8'
                : node.role === 'aggregation' ? '#38bdf8'
                    : '#10b981';
            ctx.fillStyle = ledColor;
            const leds = [[-5, -5], [0, -5], [5, -5], [-5, 0], [0, 0], [5, 0]];
            leds.slice(0, node.role === 'spine' ? 6 : node.role === 'aggregation' ? 4 : 2).forEach(([dx, dy]) => {
                ctx.fillRect(node.x + dx - 1.5, node.y + dy - 1.5, 3, 3);
            });
        }

        ctx.shadowBlur = 0;

        // Label
        ctx.font = `600 ${fontSize}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillStyle = isHovered ? '#ffffff' : '#cbd5e1';
        ctx.fillText(label, node.x, node.y + s + 12 / globalScale);

        // Role badge on hover
        if (isHovered && node.role) {
            ctx.font = `400 ${fontSize * 0.85}px Inter, sans-serif`;
            ctx.fillStyle = '#94a3b8';
            ctx.fillText(`[${node.role}]`, node.x, node.y + s + 22 / globalScale);
        }
    };

    return (
        <div ref={containerRef} className="w-full h-full bg-slate-950 relative">
            {data.nodes.length === 0 ? (
                <div className="absolute inset-0 flex items-center justify-center flex-col gap-4 text-slate-500">
                    <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                    <span className="text-sm font-medium tracking-widest uppercase">Initializing canvas…</span>
                </div>
            ) : (
                <>
                    {/* Legend */}
                    <div className="absolute top-3 left-3 bg-gray-900/80 backdrop-blur border border-gray-800 rounded-lg px-3 py-2 z-10">
                        <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1.5">Node Roles</p>
                        {[
                            { color: '#6366f1', label: 'Core Spine' },
                            { color: '#3b82f6', label: 'Aggregation' },
                            { color: '#06b6d4', label: 'Leaf Switch' },
                            { color: '#10b981', label: 'Host' },
                            { color: '#f59e0b', label: 'Router / WAN' },
                        ].map(({ color, label }) => (
                            <div key={label} className="flex items-center gap-1.5 mb-0.5">
                                <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                                <span className="text-[9px] text-gray-400">{label}</span>
                            </div>
                        ))}
                        <p className="text-[9px] text-gray-500 uppercase tracking-widest mt-2 mb-1">Links</p>
                        {[
                            { color: '#818cf8', label: 'Spine (1Gbps)', dash: false },
                            { color: '#f59e0b', label: 'Cross-Agg MP', dash: true },
                            { color: '#38bdf8', label: 'Agg→Leaf', dash: false },
                            { color: '#64748b', label: 'WAN', dash: true },
                        ].map(({ color, label, dash }) => (
                            <div key={label} className="flex items-center gap-1.5 mb-0.5">
                                <svg width="18" height="6">
                                    <line x1="0" y1="3" x2="18" y2="3" stroke={color} strokeWidth="2"
                                        strokeDasharray={dash ? '4 2' : 'none'} />
                                </svg>
                                <span className="text-[9px] text-gray-400">{label}</span>
                            </div>
                        ))}
                    </div>

                    <ForceGraph2D
                        ref={fgRef}
                        width={dims.w}
                        height={dims.h}
                        graphData={data}
                        nodeCanvasObject={drawNode}
                        nodeCanvasObjectMode={() => 'replace'}
                        onNodeHover={setHovered}
                        linkColor={l => LINK_COLOR[l.type] || '#334155'}
                        linkWidth={l => LINK_WIDTH[l.type] || 1.5}
                        linkDashArray={l => LINK_DASH[l.type] || null}
                        linkDirectionalParticles={l => ['wan', 'uplink'].includes(l.type) ? 2 : 4}
                        linkDirectionalParticleWidth={l => l.type === 'edge' ? 1.5 : 2.5}
                        linkDirectionalParticleSpeed={l => l.type === 'wan' ? 0.002 : 0.006}
                        linkDirectionalParticleColor={l => LINK_COLOR[l.type] || '#60a5fa'}
                        backgroundColor="transparent"
                        cooldownTicks={120}
                    />
                </>
            )}
        </div>
    );
}
import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function NetworkGraph({ data }) {
    const fgRef = useRef();
    const containerRef = useRef();
    const [dims, setDims] = useState({ w: 800, h: 600 });

    // Track container size
    useEffect(() => {
        const obs = new ResizeObserver(entries => {
            for (const e of entries) {
                setDims({ w: e.contentRect.width, h: e.contentRect.height });
            }
        });
        if (containerRef.current) obs.observe(containerRef.current);
        return () => obs.disconnect();
    }, []);

    // Tune forces and fit on data change
    useEffect(() => {
        if (!fgRef.current || data.nodes.length === 0) return;
        fgRef.current.d3Force('charge').strength(-400);
        fgRef.current.d3Force('link').distance(node => (node.type === 'wan' ? 180 : 120));
        setTimeout(() => fgRef.current?.zoomToFit(400, 80), 600);
    }, [data]);

    const drawNode = (node, ctx, globalScale) => {
        const label = node.label || node.name || `Node ${node.id}`;
        const fontSize = Math.max(10 / globalScale, 4);

        ctx.shadowBlur = 15;

        if (node.type === 'router') {
            // Draw Router (Hexagon / Diamond)
            const size = 16;
            ctx.shadowColor = '#f59e0b'; // Amber glow
            ctx.fillStyle = '#1e293b';
            ctx.strokeStyle = '#f59e0b';
            ctx.lineWidth = 2 / globalScale;

            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                const angle = (i * Math.PI) / 3;
                const x = node.x + size * Math.cos(angle);
                const y = node.y + size * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();

            // Router "X" icon inside
            ctx.beginPath();
            ctx.moveTo(node.x - 6, node.y - 6); ctx.lineTo(node.x + 6, node.y + 6);
            ctx.moveTo(node.x + 6, node.y - 6); ctx.lineTo(node.x - 6, node.y + 6);
            ctx.stroke();

        } else if (node.type === 'host') {
            // Draw WAN Host (Circle)
            const size = 12;
            ctx.shadowColor = '#10b981'; // Green glow
            ctx.fillStyle = '#064e3b';
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 1.5 / globalScale;

            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();

        } else {
            // Draw Switch (Square)
            const size = 14;
            ctx.shadowColor = '#3b82f6'; // Blue glow
            ctx.fillStyle = '#1e293b';
            ctx.strokeStyle = '#3b82f6';
            ctx.lineWidth = 1.5 / globalScale;

            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(node.x - size, node.y - size, size * 2, size * 2, 4);
            else ctx.rect(node.x - size, node.y - size, size * 2, size * 2);
            ctx.fill();
            ctx.stroke();

            // Port LEDs mapping
            ctx.fillStyle = '#10b981';
            const ledSize = 4;
            const gap = 3;
            [[-6, -6], [2, -6], [-6, 2], [2, 2]].forEach(([dx, dy]) => {
                ctx.fillRect(node.x + dx, node.y + dy, ledSize, ledSize);
            });
        }

        ctx.shadowBlur = 0;
        // Label
        ctx.font = `600 ${fontSize}px Inter, Sans-Serif`;
        ctx.textAlign = 'center';
        ctx.fillStyle = '#cbd5e1';
        ctx.fillText(label, node.x, node.y + 22 / globalScale);
    };

    return (
        <div ref={containerRef} className="w-full h-full bg-slate-950 relative">
            {data.nodes.length === 0 ? (
                <div className="absolute inset-0 flex items-center justify-center flex-col gap-4 text-slate-500">
                    <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                    <span className="text-sm font-medium tracking-widest uppercase">Initializing Canvas…</span>
                </div>
            ) : (
                <ForceGraph2D
                    ref={fgRef}
                    width={dims.w}
                    height={dims.h}
                    graphData={data}
                    nodeCanvasObject={drawNode}
                    nodeCanvasObjectMode={() => 'replace'}
                    linkColor={link => (link.type === 'wan' ? '#64748b' : '#334155')}
                    linkWidth={link => (link.type === 'wan' ? 1.5 : 2.5)}
                    linkDashArray={link => (link.type === 'wan' ? [5, 5] : null)}
                    linkDirectionalParticles={4}
                    linkDirectionalParticleWidth={2.5}
                    linkDirectionalParticleSpeed={link => (link.type === 'wan' ? 0.003 : 0.008)}
                    linkDirectionalParticleColor={link => (link.type === 'router' ? '#f59e0b' : '#60a5fa')}
                    backgroundColor="transparent"
                />
            )}
        </div>
    );
}

import React from 'react';
import NetworkGraph from '../components/NetworkGraph';

export default function TopologyPage({ data }) {
    return (
        <div className="h-full flex flex-col">
            {/* Page header */}
            <div className="flex-shrink-0 px-6 py-3 border-b border-gray-800 bg-gray-900/50 flex items-center justify-between">
                <div>
                    <h2 className="text-white font-semibold">Network Topology</h2>
                    <p className="text-gray-400 text-xs">
                        {data.nodes.length} switch{data.nodes.length !== 1 ? 'es' : ''} &bull;{' '}
                        {data.links.length} link{data.links.length !== 1 ? 's' : ''}
                    </p>
                </div>
                <span className="text-xs text-gray-500 font-mono">Live · 3s poll</span>
            </div>

            {/* Full-height graph */}
            <div className="flex-1 overflow-hidden">
                <NetworkGraph data={data} />
            </div>
        </div>
    );
}

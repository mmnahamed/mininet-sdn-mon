import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import TopologyPage from './pages/TopologyPage';
import DashboardPage from './pages/DashboardPage';

const API_BASE_URL = 'http://192.168.233.140:8000/api/network';
const POLL_INTERVAL = 3000;

export default function App() {
    const [graphData, setGraphData] = useState({ nodes: [], links: [] });
    const [metricsData, setMetricsData] = useState({});
    const [status, setStatus] = useState('connecting'); // 'ok' | 'connecting' | 'error'

    const fetchData = useCallback(async () => {
        try {
            const [graphRes, metricsRes] = await Promise.all([
                fetch(`${API_BASE_URL}/graph`),
                fetch(`${API_BASE_URL}/metrics`)
            ]);
            if (!graphRes.ok || !metricsRes.ok) throw new Error('API error');

            const newGraph = await graphRes.json();
            const newMetrics = await metricsRes.json();

            setGraphData(prev => {
                const sameSize =
                    prev.nodes.length === newGraph.nodes.length &&
                    prev.links.length === newGraph.links.length;
                return sameSize ? prev : newGraph;
            });
            setMetricsData(newMetrics);
            setStatus(newGraph.nodes.length > 0 ? 'ok' : 'connecting');
        } catch {
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        fetchData();
        const id = setInterval(fetchData, POLL_INTERVAL);
        return () => clearInterval(id);
    }, [fetchData]);

    return (
        <BrowserRouter>
            <Routes>
                <Route element={<Layout status={status} />}>
                    <Route index element={<Navigate to="/dashboard" replace />} />
                    <Route
                        path="/dashboard"
                        element={<DashboardPage metrics={metricsData} nodes={graphData.nodes} />}
                    />
                    <Route
                        path="/topology"
                        element={<TopologyPage data={graphData} />}
                    />
                </Route>
            </Routes>
        </BrowserRouter>
    );
}

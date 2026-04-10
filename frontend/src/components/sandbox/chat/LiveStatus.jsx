import { useState, useEffect } from 'react';
import api from '../../../api/axios';

const LiveStatus = () => {
  const [toolCount, setToolCount] = useState(0);
  const [kbConnected, setKbConnected] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await api.get('/tools/connections/');
        const connections = res.data?.results || res.data || [];
        const connected = connections.filter(c => c.status === 'connected' && c.enabled);
        setToolCount(connected.length);
        setKbConnected(connected.some(c =>
          c.tool_card?.slug === 'rag-search' || c.tool_slug === 'rag-search'
        ));
      } catch (_) {
        // Silent fail — non-critical UI element
      }
    };
    fetchStatus();
  }, []);

  if (toolCount === 0) return null;

  return (
    <div className="flex items-center gap-1.5 text-[10px] text-gray-400 dark:text-gray-500">
      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      <span>Jeevs active</span>
      {kbConnected && (
        <>
          <span className="text-gray-300 dark:text-gray-600">·</span>
          <span>Knowledge Base connected</span>
        </>
      )}
      <span className="text-gray-300 dark:text-gray-600">·</span>
      <span>{toolCount} tool{toolCount !== 1 ? 's' : ''} ready</span>
    </div>
  );
};

export default LiveStatus;

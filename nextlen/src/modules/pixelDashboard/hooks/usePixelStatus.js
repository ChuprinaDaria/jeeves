import { useState, useEffect, useRef } from 'react';
import { clientAPI } from '../../../api/client';
import { POLLING_INTERVAL } from '../constants';

export default function usePixelStatus(enabled) {
  const [status, setStatus] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;

    const fetchStatus = async () => {
      try {
        const response = await clientAPI.getPixelStatus();
        setStatus(response.data);
      } catch {
        // Keep last known status on error
      }
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, POLLING_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled]);

  return status;
}

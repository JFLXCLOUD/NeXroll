import { useEffect, useState } from 'react';

export default function useHealthSummary(url, schedulerRunning, prerollCount, activeCategory) {
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    let cancelled = false;
    let pending = false;
    let controller;
    const refresh = async () => {
      if (pending) return;
      pending = true;
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      try {
        const response = await fetch(url, { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error('Health check unavailable');
        const data = await response.json();
        if (!data || !Array.isArray(data.checks) || !data.status) throw new Error('Invalid health check');
        if (!cancelled) setSummary(data);
      } catch {
        // Never leave an old green result on screen when the check fails.
        if (!cancelled) setSummary({
          score: null, status: 'attention', attention_count: 1, checks: [],
          note: 'Unable to refresh system health. Check the connection to NeXroll.',
        });
      } finally {
        clearTimeout(timeout);
        pending = false;
      }
    };
    refresh();
    const interval = setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener('focus', refresh);
      controller?.abort();
    };
  }, [url, schedulerRunning, prerollCount, activeCategory]);
  return summary;
}

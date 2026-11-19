import { useEffect, useState } from 'react';

export interface FREDDataPoint {
  date: string;
  DGS10?: number;
  T10Y2Y?: number;
  BAMLH0A0HYM2?: number;
  STLFSI4?: number;
}

export const useFREDMetrics = () => {
  const [metrics, setMetrics] = useState<FREDDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/v1/fred/metrics')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setMetrics)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { metrics, loading, error };
};

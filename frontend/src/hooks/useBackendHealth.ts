import { useEffect, useState } from 'react';

export const useBackendHealth = () => {
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    fetch('/api/v1/healthz')
      .then((r) => r.json())
      .then((data) => setReady(data.status === 'ok'))
      .catch(() => setReady(false));
  }, []);

  return ready;
};

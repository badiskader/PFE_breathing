import { useQuery } from '@tanstack/react-query';

import { getPredictions } from '@/api';
import { mockPredictionsBySensorId } from '@/mock';

export function usePredictions(sensorId: string) {
  const fallback = mockPredictionsBySensorId[sensorId];

  return useQuery({
    queryKey: ['predictions', sensorId],
    queryFn: async () => {
      try {
        return await getPredictions(sensorId);
      } catch {
        return fallback;
      }
    },
    initialData: fallback,
    refetchInterval: 60_000,
  });
}

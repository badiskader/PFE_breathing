import { useQuery } from '@tanstack/react-query';

import { getDashboardRecommendation } from '@/api';
import { mockDashboardRecommendationsBySensorId } from '@/mock';

export function useRecommendation(userId: string, sensorId: string) {
  const fallback = mockDashboardRecommendationsBySensorId[sensorId];

  return useQuery({
    queryKey: ['recommendations', 'dashboard', userId, sensorId],
    queryFn: async () => {
      try {
        return await getDashboardRecommendation(userId, sensorId);
      } catch {
        return fallback;
      }
    },
    initialData: fallback,
    refetchInterval: 60_000,
  });
}

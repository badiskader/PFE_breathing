import { apiRequest } from './client';
import type { DashboardRecommendation } from '@/types';

export function getDashboardRecommendation(userId: string, sensorId: string) {
  const query = new URLSearchParams({ user_id: userId, sensor_id: sensorId });
  return apiRequest<DashboardRecommendation>(`/recommendations/dashboard?${query.toString()}`);
}

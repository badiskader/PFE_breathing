import { apiRequest } from './client';
import type { PredictionResponse } from '@/types';

export function getPredictions(sensorId: string) {
  return apiRequest<PredictionResponse>(`/predictions?sensor_id=${encodeURIComponent(sensorId)}`);
}

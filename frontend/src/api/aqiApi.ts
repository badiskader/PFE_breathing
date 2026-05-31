import { apiRequest } from './client';
import type { AQISensorsResponse, SensorAQI } from '@/types';

export function getCurrentAQI(sensorId: string) {
  return apiRequest<SensorAQI>(`/aqi/current?sensor_id=${encodeURIComponent(sensorId)}`);
}

export function getSensorsAQI() {
  return apiRequest<AQISensorsResponse>('/aqi/sensors');
}

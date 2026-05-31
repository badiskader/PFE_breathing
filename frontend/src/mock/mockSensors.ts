import type { AQISensorsResponse, SensorAQI } from '@/types';

export const mockCurrentSensors = [
  {
    sensor_id: 'AQ_CST_01',
    timestamp: '2025-05-21T19:00:00Z',
    aqi_score: 22,
    aqi_category: 'Good',
    risk_level: 'low',
    dominant_pollutant: 'PM25',
    sub_indices: {
      PM25: 22,
      PM10: 18,
      NO2: 15,
      SO2: 8,
      CO: 11,
      O3: 31,
    },
  },
  {
    sensor_id: 'AQ_CST_02',
    timestamp: '2025-05-21T19:00:00Z',
    aqi_score: 67,
    aqi_category: 'Moderate',
    risk_level: 'moderate',
    dominant_pollutant: 'PM25',
    sub_indices: {
      PM25: 67,
      PM10: 38,
      NO2: 15,
      SO2: 8,
      CO: 45,
      O3: 31,
    },
  },
  {
    sensor_id: 'AQ_CST_03',
    timestamp: '2025-05-21T19:00:00Z',
    aqi_score: 112,
    aqi_category: 'Unhealthy for Sensitive Groups',
    risk_level: 'high',
    dominant_pollutant: 'PM25',
    sub_indices: {
      PM25: 112,
      PM10: 74,
      NO2: 39,
      SO2: 25,
      CO: 58,
      O3: 46,
    },
  },
] satisfies SensorAQI[];

export const mockSensorsResponse = {
  count: mockCurrentSensors.length,
  sensors: mockCurrentSensors,
} satisfies AQISensorsResponse;

export const mockCurrentAqiBySensorId = Object.fromEntries(
  mockCurrentSensors.map((sensor) => [sensor.sensor_id, sensor]),
) as Record<string, SensorAQI>;

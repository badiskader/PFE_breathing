import { useQuery } from '@tanstack/react-query';

import { getCurrentAQI } from '@/api';
import {
  mockCurrentAqiBySensorId,
  mockPollutantsBySensorId,
  mockSensorTable,
  mockWeatherBySensorId,
} from '@/mock';
import type { SensorAQI } from '@/types';

function enrichSensorAQI(sensor: SensorAQI): SensorAQI {
  const tableEntry = mockSensorTable[sensor.sensor_id];
  const weather = mockWeatherBySensorId[sensor.sensor_id];
  const pollutants = mockPollutantsBySensorId[sensor.sensor_id];

  return {
    ...sensor,
    latitude: sensor.latitude ?? tableEntry?.latitude,
    longitude: sensor.longitude ?? tableEntry?.longitude,
    name: sensor.name ?? tableEntry?.name,
    pollutants: sensor.pollutants ?? pollutants,
    weather: sensor.weather ?? weather,
  };
}

export function useCurrentAQI(sensorId: string) {
  const fallback = enrichSensorAQI(mockCurrentAqiBySensorId[sensorId]);

  return useQuery({
    queryKey: ['aqi', 'current', sensorId],
    queryFn: async () => {
      try {
        return enrichSensorAQI(await getCurrentAQI(sensorId));
      } catch {
        return fallback;
      }
    },
    initialData: fallback,
    refetchInterval: 60_000,
  });
}

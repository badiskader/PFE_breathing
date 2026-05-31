import { useQuery } from '@tanstack/react-query';

import { getSensorsAQI } from '@/api';
import {
  mockPollutantsBySensorId,
  mockSensorsResponse,
  mockSensorTable,
  mockWeatherBySensorId,
} from '@/mock';
import type { AQISensorsResponse, SensorAQI } from '@/types';

function enrichSensorAQI(sensor: SensorAQI): SensorAQI {
  const tableEntry = mockSensorTable[sensor.sensor_id];
  const pollutants = mockPollutantsBySensorId[sensor.sensor_id];
  const weather = mockWeatherBySensorId[sensor.sensor_id];

  return {
    ...sensor,
    latitude: sensor.latitude ?? tableEntry?.latitude,
    longitude: sensor.longitude ?? tableEntry?.longitude,
    name: sensor.name ?? tableEntry?.name,
    pollutants: sensor.pollutants ?? pollutants,
    weather: sensor.weather ?? weather,
  };
}

function enrichSensorsResponse(response: AQISensorsResponse): AQISensorsResponse {
  const sensors = response.sensors.map(enrichSensorAQI);

  return {
    ...response,
    count: sensors.length,
    sensors,
  };
}

export function useSensorsAQI() {
  const fallback = enrichSensorsResponse(mockSensorsResponse);

  return useQuery({
    queryKey: ['aqi', 'sensors'],
    queryFn: async () => {
      try {
        return enrichSensorsResponse(await getSensorsAQI());
      } catch {
        return fallback;
      }
    },
    initialData: fallback,
    refetchInterval: 60_000,
  });
}

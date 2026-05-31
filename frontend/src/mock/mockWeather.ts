import type { WeatherSnapshot } from '@/types';

export const mockWeatherBySensorId: Record<string, WeatherSnapshot> = {
  AQ_CST_01: {
    temperature_2m: 22,
    relative_humidity_2m: 65,
    wind_speed_10m: 11,
    wind_direction_10m: 84,
    source: 'mock',
  },
  AQ_CST_02: {
    temperature_2m: 21,
    relative_humidity_2m: 67,
    wind_speed_10m: 9,
    wind_direction_10m: 76,
    source: 'mock',
  },
  AQ_CST_03: {
    temperature_2m: 24,
    relative_humidity_2m: 58,
    wind_speed_10m: 15,
    wind_direction_10m: 61,
    source: 'mock',
  },
};

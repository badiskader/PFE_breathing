export type AQICategory =
  | 'Good'
  | 'Moderate'
  | 'Unhealthy for Sensitive Groups'
  | 'Unhealthy'
  | 'Very Unhealthy'
  | 'Hazardous';

export type RiskLevel = 'low' | 'moderate' | 'high' | 'very_high' | 'severe';

export type PollutantKey = 'PM25' | 'PM10' | 'NO2' | 'SO2' | 'CO' | 'O3';

export type PollutantRecord<T = number> = Record<PollutantKey, T>;

export type WeatherSnapshot = {
  temperature_2m: number;
  relative_humidity_2m: number;
  wind_speed_10m: number;
  wind_direction_10m: number;
  source: 'backend' | 'mock';
};

export type SensorAQI = {
  sensor_id: string;
  timestamp: string;
  aqi_score: number;
  aqi_category: AQICategory;
  risk_level: RiskLevel;
  dominant_pollutant: PollutantKey;
  sub_indices: PollutantRecord;
  latitude?: number;
  longitude?: number;
  name?: string;
  pollutants?: PollutantRecord;
  weather?: WeatherSnapshot;
};

export type AQISensorsResponse = {
  count: number;
  sensors: SensorAQI[];
};

export type SensorTableEntry = {
  sensor_id: string;
  name: string;
  latitude: number;
  longitude: number;
  radius_km: number;
};

export const pollutantKeys: PollutantKey[] = ['PM25', 'PM10', 'NO2', 'SO2', 'CO', 'O3'];

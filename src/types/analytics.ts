import type { PollutantKey, PollutantRecord } from './aqi';

export type AnalyticsRange = '24h' | '7d' | '30d';

export type AQITrendPoint = {
  timestamp: string;
  aqi: number;
};

export type AQITrendResponse = {
  sensor_id: string;
  range: AnalyticsRange;
  points: AQITrendPoint[];
  avg_aqi: number;
  peak_aqi: number;
  worst_day: string;
};

export type SensorComparisonPoint = {
  sensor_id: string;
  name: string;
  aqi: number;
};

export type SensorComparisonResponse = {
  range: AnalyticsRange;
  sensors: SensorComparisonPoint[];
};

export type PollutantStackedBar = {
  label: string;
  values: PollutantRecord;
};

export type AnalyticsInsight = {
  insight_id: string;
  title: string;
  pollutant?: PollutantKey;
};

export type AnalyticsMockBundle = {
  range: AnalyticsRange;
  trend: AQITrendResponse;
  sensorComparison: SensorComparisonResponse;
  pollutantBars: PollutantStackedBar[];
  insights: AnalyticsInsight[];
};

import type { AQICategory } from './aqi';

export type ForecastPoint = {
  hour_offset: number;
  timestamp: string;
  PM25: number;
  PM10: number;
  NO2: number;
  SO2: number;
  CO: number;
  O3: number;
  predicted_aqi: number;
  predicted_category: AQICategory;
};

export type PredictionResponse = {
  sensor_id: string;
  generated_at: string;
  forecast_horizon_hours: 12;
  predictions: ForecastPoint[];
};

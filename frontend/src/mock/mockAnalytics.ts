import type { AnalyticsMockBundle, AnalyticsRange } from '@/types';

const trendPoints24h = [
  { timestamp: '2026-05-21T00:00:00Z', aqi: 58 },
  { timestamp: '2026-05-21T02:00:00Z', aqi: 72 },
  { timestamp: '2026-05-21T04:00:00Z', aqi: 84 },
  { timestamp: '2026-05-21T06:00:00Z', aqi: 64 },
  { timestamp: '2026-05-21T08:00:00Z', aqi: 48 },
  { timestamp: '2026-05-21T10:00:00Z', aqi: 36 },
  { timestamp: '2026-05-21T12:00:00Z', aqi: 32 },
  { timestamp: '2026-05-21T14:00:00Z', aqi: 22 },
  { timestamp: '2026-05-21T16:00:00Z', aqi: 20 },
  { timestamp: '2026-05-21T18:00:00Z', aqi: 42 },
];

export const mockAnalyticsByRange = {
  '24h': {
    range: '24h',
    trend: {
      sensor_id: 'AQ_CST_01',
      range: '24h',
      points: trendPoints24h,
      avg_aqi: 64,
      peak_aqi: 112,
      worst_day: 'Wednesday',
    },
    sensorComparison: {
      range: '24h',
      sensors: [
        { sensor_id: 'AQ_CST_03', name: 'El Harrach', aqi: 112 },
        { sensor_id: 'AQ_CST_02', name: 'Bab El Oued', aqi: 67 },
        { sensor_id: 'AQ_CST_01', name: 'Centre Ville', aqi: 22 },
      ],
    },
    pollutantBars: [
      { label: '4h', values: { PM25: 42, PM10: 21, NO2: 16, SO2: 10, CO: 8, O3: 4 } },
      { label: '8h', values: { PM25: 40, PM10: 20, NO2: 14, SO2: 9, CO: 7, O3: 10 } },
      { label: '12h', values: { PM25: 34, PM10: 20, NO2: 14, SO2: 8, CO: 7, O3: 17 } },
      { label: '16h', values: { PM25: 31, PM10: 19, NO2: 12, SO2: 8, CO: 6, O3: 24 } },
      { label: '20h', values: { PM25: 33, PM10: 21, NO2: 13, SO2: 8, CO: 7, O3: 18 } },
    ],
    insights: [
      { insight_id: 'insight_cleanest_hour', title: 'Cleanest hour today: 06:00 (AQI 12)' },
      { insight_id: 'insight_worst_pollutant', title: 'Worst pollutant this week: PM2.5', pollutant: 'PM25' },
      { insight_id: 'insight_aqi_rise', title: 'AQI rose 23% in the last 24h' },
    ],
  },
  '7d': {
    range: '7d',
    trend: {
      sensor_id: 'AQ_CST_01',
      range: '7d',
      points: [
        { timestamp: '2026-05-15T00:00:00Z', aqi: 42 },
        { timestamp: '2026-05-16T00:00:00Z', aqi: 50 },
        { timestamp: '2026-05-17T00:00:00Z', aqi: 74 },
        { timestamp: '2026-05-18T00:00:00Z', aqi: 62 },
        { timestamp: '2026-05-19T00:00:00Z', aqi: 55 },
        { timestamp: '2026-05-20T00:00:00Z', aqi: 48 },
        { timestamp: '2026-05-21T00:00:00Z', aqi: 64 },
      ],
      avg_aqi: 56,
      peak_aqi: 92,
      worst_day: 'Tuesday',
    },
    sensorComparison: {
      range: '7d',
      sensors: [
        { sensor_id: 'AQ_CST_03', name: 'El Harrach', aqi: 96 },
        { sensor_id: 'AQ_CST_02', name: 'Bab El Oued', aqi: 72 },
        { sensor_id: 'AQ_CST_01', name: 'Centre Ville', aqi: 56 },
      ],
    },
    pollutantBars: [
      { label: 'Mon', values: { PM25: 35, PM10: 22, NO2: 14, SO2: 8, CO: 7, O3: 14 } },
      { label: 'Tue', values: { PM25: 40, PM10: 21, NO2: 16, SO2: 9, CO: 8, O3: 6 } },
      { label: 'Wed', values: { PM25: 34, PM10: 20, NO2: 15, SO2: 8, CO: 8, O3: 15 } },
    ],
    insights: [
      { insight_id: 'insight_week_peak', title: 'Highest weekly AQI occurred Tuesday evening' },
      { insight_id: 'insight_pm25_week', title: 'PM2.5 dominated most weekly peaks', pollutant: 'PM25' },
    ],
  },
  '30d': {
    range: '30d',
    trend: {
      sensor_id: 'AQ_CST_01',
      range: '30d',
      points: [
        { timestamp: '2026-04-22T00:00:00Z', aqi: 55 },
        { timestamp: '2026-04-29T00:00:00Z', aqi: 68 },
        { timestamp: '2026-05-06T00:00:00Z', aqi: 74 },
        { timestamp: '2026-05-13T00:00:00Z', aqi: 61 },
        { timestamp: '2026-05-21T00:00:00Z', aqi: 64 },
      ],
      avg_aqi: 62,
      peak_aqi: 118,
      worst_day: 'May 6',
    },
    sensorComparison: {
      range: '30d',
      sensors: [
        { sensor_id: 'AQ_CST_03', name: 'El Harrach', aqi: 104 },
        { sensor_id: 'AQ_CST_02', name: 'Bab El Oued', aqi: 78 },
        { sensor_id: 'AQ_CST_01', name: 'Centre Ville', aqi: 62 },
      ],
    },
    pollutantBars: [
      { label: 'W1', values: { PM25: 36, PM10: 22, NO2: 15, SO2: 8, CO: 7, O3: 12 } },
      { label: 'W2', values: { PM25: 39, PM10: 20, NO2: 14, SO2: 9, CO: 8, O3: 10 } },
      { label: 'W3', values: { PM25: 34, PM10: 21, NO2: 13, SO2: 8, CO: 8, O3: 16 } },
      { label: 'W4', values: { PM25: 32, PM10: 19, NO2: 12, SO2: 8, CO: 7, O3: 22 } },
    ],
    insights: [
      { insight_id: 'insight_monthly_average', title: 'Monthly AQI stayed mostly moderate' },
      { insight_id: 'insight_monthly_o3', title: 'O3 contribution increased on clearer afternoons', pollutant: 'O3' },
    ],
  },
} satisfies Record<AnalyticsRange, AnalyticsMockBundle>;

export const mockAnalytics = mockAnalyticsByRange['24h'];

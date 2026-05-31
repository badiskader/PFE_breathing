import type { DashboardRecommendation } from '@/types';

export const mockDashboardRecommendation = {
  sensor_id: 'AQ_CST_01',
  vulnerability_category: 'générale',
  generated_at: '2026-05-21T19:00:00Z',
  forecast_aqi_max: 42,
  forecast_category: 'Good',
  rule_output: {
    vulnerability_category: 'générale',
    forecast_aqi_max: 42,
    forecast_category: 'Good',
    aqi_trajectory: 'stable',
    flagged_pollutants: ['PM25', 'O3'],
    urgency_level: 'safe',
    key_risks: [
      'Low short-term exposure risk',
      'Outdoor activity is favorable',
    ],
    pollutant_scores: {
      PM25: 2,
      PM10: 1,
      NO2: 1,
      SO2: 0,
      CO: 0,
      O3: 1,
    },
    pollutant_max_values: {
      PM25: 7.8,
      PM10: 15,
      NO2: 9,
      SO2: 4.2,
      CO: 161,
      O3: 36,
    },
  },
  recommendation_text:
    "La qualité de l'air est bonne. Profitez d'une activité en plein air. Les conditions sont favorables pour toutes les activités sportives, même intenses.",
} satisfies DashboardRecommendation;

export const mockDashboardRecommendationsBySensorId: Record<string, DashboardRecommendation> = {
  AQ_CST_01: mockDashboardRecommendation,
  AQ_CST_02: {
    ...mockDashboardRecommendation,
    sensor_id: 'AQ_CST_02',
    forecast_aqi_max: 108,
    forecast_category: 'Unhealthy for Sensitive Groups',
    rule_output: {
      ...mockDashboardRecommendation.rule_output,
      forecast_aqi_max: 108,
      forecast_category: 'Unhealthy for Sensitive Groups',
      aqi_trajectory: 'stable',
      pollutant_max_values: {
        PM25: 22.9,
        PM10: 31,
        NO2: 36.1,
        SO2: 8,
        CO: 250,
        O3: 40,
      },
    },
    recommendation_text:
      "La station Bab El Oued reste en niveau modere avec une hausse possible des PM2.5. Privilegiez les sorties courtes et surveillez les alertes.",
  },
  AQ_CST_03: {
    ...mockDashboardRecommendation,
    sensor_id: 'AQ_CST_03',
    forecast_aqi_max: 161,
    forecast_category: 'Unhealthy',
    rule_output: {
      ...mockDashboardRecommendation.rule_output,
      forecast_aqi_max: 161,
      forecast_category: 'Unhealthy',
      aqi_trajectory: 'rising',
      flagged_pollutants: ['PM25', 'NO2'],
      urgency_level: 'avoid',
      pollutant_scores: {
        PM25: 3,
        PM10: 2,
        NO2: 2,
        SO2: 1,
        CO: 1,
        O3: 1,
      },
      pollutant_max_values: {
        PM25: 39.4,
        PM10: 56.1,
        NO2: 66.4,
        SO2: 14.8,
        CO: 352,
        O3: 56,
      },
    },
    recommendation_text:
      "La pollution pourrait atteindre un niveau defavorable pour les personnes sensibles pres de cette station. Reduisez les efforts dehors et gardez un masque disponible.",
  },
};

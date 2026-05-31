import type { AQICategory, PollutantKey, PollutantRecord } from './aqi';

export type VulnerabilityCategory = 'generale' | 'sensible' | 'vulnerable';

export type BackendVulnerabilityCategory = 'générale' | 'sensible' | 'vulnérable';

export type UrgencyLevel = 'safe' | 'caution' | 'avoid' | 'danger';

export type AQITrajectory = 'rising' | 'stable' | 'falling';

export type RuleOutput = {
  vulnerability_category: BackendVulnerabilityCategory;
  forecast_aqi_max: number;
  forecast_category: AQICategory;
  aqi_trajectory: AQITrajectory;
  flagged_pollutants: PollutantKey[];
  urgency_level: UrgencyLevel;
  key_risks: string[];
  pollutant_scores: PollutantRecord<0 | 1 | 2 | 3>;
  pollutant_max_values: PollutantRecord;
};

export type DashboardRecommendation = {
  sensor_id: string;
  vulnerability_category: BackendVulnerabilityCategory;
  generated_at: string;
  forecast_aqi_max: number;
  forecast_category: AQICategory;
  rule_output: RuleOutput;
  recommendation_text: string;
};

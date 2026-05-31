import { aqiColors, colors } from '@/theme';
import type { AQICategory, RiskLevel, UrgencyLevel } from '@/types';

export function getAQIColor(category: AQICategory) {
  return aqiColors[category] ?? colors.goodGreen;
}

export function getAQITextColor(category: AQICategory) {
  const textColors: Record<AQICategory, string> = {
    Good: '#275E0B',
    Moderate: '#7A5A00',
    'Unhealthy for Sensitive Groups': '#8B3A00',
    Unhealthy: '#7F1D1D',
    'Very Unhealthy': '#31135F',
    Hazardous: '#3F0B0B',
  };

  return textColors[category];
}

export function getAQISubtleTextColor(category: AQICategory) {
  const subtleColors: Record<AQICategory, string> = {
    Good: 'rgba(45, 102, 15, 0.64)',
    Moderate: 'rgba(122, 90, 0, 0.66)',
    'Unhealthy for Sensitive Groups': 'rgba(139, 58, 0, 0.66)',
    Unhealthy: 'rgba(127, 29, 29, 0.66)',
    'Very Unhealthy': 'rgba(49, 19, 95, 0.66)',
    Hazardous: 'rgba(63, 11, 11, 0.66)',
  };

  return subtleColors[category];
}

export function getAQILabel(category: AQICategory) {
  return category;
}

export function getRiskLabel(riskLevel: RiskLevel | UrgencyLevel) {
  const labels: Record<string, string> = {
    avoid: 'Risque eleve',
    caution: 'Risque modere',
    danger: 'Danger',
    high: 'High risk',
    low: 'Faible risque',
    moderate: 'Moderate risk',
    safe: 'Faible risque',
    severe: 'Severe risk',
    very_high: 'Very high risk',
  };

  return labels[riskLevel] ?? riskLevel;
}

export function getUrgencyColor(urgencyLevel: UrgencyLevel) {
  const colorsByUrgency: Record<UrgencyLevel, string> = {
    avoid: colors.unhealthyOrange,
    caution: colors.moderateYellow,
    danger: colors.dangerousRed,
    safe: colors.goodGreen,
  };

  return colorsByUrgency[urgencyLevel];
}

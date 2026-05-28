import type { PollutantKey } from '@/types';

const displayNames: Record<PollutantKey, string> = {
  CO: 'CO',
  NO2: 'NO₂',
  O3: 'O3',
  PM10: 'PM10',
  PM25: 'PM2.5',
  SO2: 'SO2',
};

export function displayPollutantName(pollutant: PollutantKey) {
  return displayNames[pollutant];
}

export function displayPollutantUnit(pollutant: PollutantKey) {
  return pollutant === 'CO' ? 'ppb' : 'µg/m³';
}

export function formatPollutantValue(value: number, maximumFractionDigits = 1) {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits,
    minimumFractionDigits: maximumFractionDigits,
  }).format(value);
}

export function formatCompactPollutantValue(value: number) {
  return Number.isInteger(value) ? `${value}` : value.toFixed(1);
}

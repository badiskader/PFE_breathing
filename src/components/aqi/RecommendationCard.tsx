import { StyleSheet, Text, View } from 'react-native';

import { colors, shadows } from '@/theme';
import type { DashboardRecommendation } from '@/types';
import { getRiskLabel } from '@/utils/aqiDisplay';
import { displayPollutantName } from '@/utils/pollutantFormat';

type RecommendationCardProps = {
  recommendation: DashboardRecommendation;
};

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const forecastLabel = recommendation.rule_output.forecast_category === 'Good' ? 'Bon' : recommendation.rule_output.forecast_category;
  const trajectoryLabel =
    recommendation.rule_output.aqi_trajectory === 'stable'
      ? 'stable'
      : recommendation.rule_output.aqi_trajectory === 'rising'
        ? 'en hausse'
        : 'en baisse';

  return (
    <View style={styles.card}>
      <View style={styles.leftRail} />
      <View style={styles.content}>
        <View style={styles.chips}>
          <View style={[styles.chip, styles.populationChip]}>
            <Text style={[styles.chipText, styles.populationText]}>Population générale</Text>
          </View>
          <View style={[styles.chip, styles.riskChip]}>
            <Text style={[styles.chipText, styles.riskText]}>
              {getRiskLabel(recommendation.rule_output.urgency_level)}
            </Text>
          </View>
        </View>
        <Text style={styles.forecast}>Prévision: {forecastLabel}, {trajectoryLabel}</Text>
        <Text style={styles.body}>{recommendation.recommendation_text}</Text>
        <View style={styles.pollutants}>
          {recommendation.rule_output.flagged_pollutants.map((pollutant) => (
            <View key={pollutant} style={styles.pollutantChip}>
              <Text style={styles.pollutantText}>{displayPollutantName(pollutant)}</Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: {
    color: '#374151',
    fontSize: 13,
    letterSpacing: 0,
    lineHeight: 20,
  },
  card: {
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 24,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    minHeight: 158,
    overflow: 'hidden',
    ...shadows.card,
  },
  chip: {
    borderRadius: 18,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chipText: {
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 18,
  },
  content: {
    flex: 1,
    paddingBottom: 12,
    paddingLeft: 18,
    paddingRight: 14,
    paddingTop: 12,
  },
  forecast: {
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 7,
  },
  leftRail: {
    backgroundColor: colors.goodGreen,
    width: 5,
  },
  pollutantChip: {
    backgroundColor: '#F1F3F6',
    borderRadius: 18,
    paddingHorizontal: 11,
    paddingVertical: 3,
  },
  pollutants: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  pollutantText: {
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 18,
  },
  populationChip: {
    backgroundColor: '#EEF5FF',
  },
  populationText: {
    color: '#0B57FF',
  },
  riskChip: {
    backgroundColor: '#EAF9EF',
  },
  riskText: {
    color: '#008B35',
  },
});

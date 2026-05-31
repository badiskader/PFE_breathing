import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { colors, shadows } from '@/theme';
import type { SensorAQI } from '@/types';
import { getAQIColor, getAQISubtleTextColor, getAQITextColor } from '@/utils/aqiDisplay';
import { displayPollutantName, displayPollutantUnit, formatPollutantValue } from '@/utils/pollutantFormat';

type AQICardProps = {
  sensor: SensorAQI;
};

export function AQICard({ sensor }: AQICardProps) {
  const pollutantName = displayPollutantName(sensor.dominant_pollutant);
  const pollutantValue = sensor.pollutants?.[sensor.dominant_pollutant] ?? sensor.sub_indices[sensor.dominant_pollutant];
  const cardColor = getAQIColor(sensor.aqi_category);
  const textColor = getAQITextColor(sensor.aqi_category);
  const subtleTextColor = getAQISubtleTextColor(sensor.aqi_category);

  return (
    <View style={[styles.card, { backgroundColor: cardColor }]}>
      <View style={styles.topRow}>
        <View style={styles.scoreBlock}>
          <Text style={[styles.score, { color: textColor }]}>{sensor.aqi_score}</Text>
          <Text style={[styles.scoreLabel, { color: textColor }]}>US AQI</Text>
        </View>
        <View style={styles.centerBlock}>
          <Text style={[styles.category, { color: textColor }]}>{sensor.aqi_category}</Text>
          <Text style={[styles.subtitle, { color: subtleTextColor }]}>Air Quality Index</Text>
        </View>
        <View style={styles.faceWrap}>
          <Ionicons color="#050505" name="happy-outline" size={75} />
        </View>
      </View>
      <View style={[styles.divider, { backgroundColor: subtleTextColor }]} />
      <View style={styles.bottomRow}>
        <Text style={[styles.pollutantLabel, { color: textColor }]}>Main pollutant: {pollutantName}</Text>
        <Text style={[styles.pollutantValue, { color: textColor }]}>
          {formatPollutantValue(pollutantValue)} {displayPollutantUnit(sensor.dominant_pollutant)}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bottomRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  card: {
    borderRadius: 24,
    height: 142,
    paddingBottom: 14,
    paddingHorizontal: 16,
    paddingTop: 14,
    ...shadows.soft,
  },
  category: {
    fontSize: 29,
    fontWeight: '800',
    letterSpacing: 0,
    lineHeight: 34,
    textAlign: 'center',
  },
  centerBlock: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
    paddingTop: 3,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    marginBottom: 11,
    marginTop: 8,
  },
  faceWrap: {
    alignItems: 'flex-end',
    justifyContent: 'center',
    width: 82,
  },
  pollutantLabel: {
    fontSize: 17,
    letterSpacing: 0,
  },
  pollutantValue: {
    fontSize: 17,
    letterSpacing: 0,
  },
  score: {
    fontSize: 61,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 61,
  },
  scoreBlock: {
    justifyContent: 'center',
    width: 104,
  },
  scoreLabel: {
    fontSize: 16,
    lineHeight: 18,
  },
  subtitle: {
    fontSize: 17,
    lineHeight: 24,
    marginTop: 7,
    textAlign: 'center',
  },
  topRow: {
    alignItems: 'center',
    flexDirection: 'row',
    height: 78,
  },
});

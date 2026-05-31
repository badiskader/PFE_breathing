import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, shadows } from '@/theme';
import type { AQICategory, ForecastPoint, PollutantKey, PollutantRecord, SensorAQI } from '@/types';
import { getAQIColor, getAQITextColor } from '@/utils/aqiDisplay';
import { formatHour } from '@/utils/dateFormat';
import { displayPollutantName, formatCompactPollutantValue } from '@/utils/pollutantFormat';

type ForecastCarouselProps = {
  current: SensorAQI;
  points: ForecastPoint[];
};

type ForecastCardItem = {
  aqi: number;
  category: AQICategory;
  pollutants: PollutantRecord;
  timestamp: string;
};

const forecastPollutants: PollutantKey[] = ['PM25', 'PM10', 'NO2', 'SO2', 'CO', 'O3'];

export function ForecastCarousel({ current, points }: ForecastCarouselProps) {
  const currentItem: ForecastCardItem = {
    aqi: current.aqi_score,
    category: current.aqi_category,
    pollutants: {
      CO: current.pollutants?.CO ?? current.sub_indices.CO,
      NO2: current.pollutants?.NO2 ?? current.sub_indices.NO2,
      O3: current.pollutants?.O3 ?? current.sub_indices.O3,
      PM10: current.pollutants?.PM10 ?? current.sub_indices.PM10,
      PM25: current.pollutants?.PM25 ?? current.sub_indices.PM25,
      SO2: current.pollutants?.SO2 ?? current.sub_indices.SO2,
    },
    timestamp: current.timestamp,
  };
  const items: ForecastCardItem[] = [
    currentItem,
    ...points.map((point) => ({
      aqi: point.predicted_aqi,
      category: point.predicted_category,
      pollutants: {
        CO: point.CO,
        NO2: point.NO2,
        O3: point.O3,
        PM10: point.PM10,
        PM25: point.PM25,
        SO2: point.SO2,
      },
      timestamp: point.timestamp,
    })),
  ];

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.content}
    >
      {items.map((item) => (
        <View key={item.timestamp} style={styles.card}>
          <Text style={styles.hour}>{formatHour(item.timestamp)}</Text>
          <View style={[styles.badge, { backgroundColor: getAQIColor(item.category) }]}>
            <Text style={[styles.badgeText, { color: getAQITextColor(item.category) }]}>{item.aqi}</Text>
          </View>
          <View style={styles.pollutantRows}>
            {forecastPollutants.map((pollutant) => (
              <ForecastRow
                key={pollutant}
                label={displayPollutantName(pollutant)}
                value={formatCompactPollutantValue(item.pollutants[pollutant])}
              />
            ))}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

function ForecastRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignItems: 'center',
    alignSelf: 'center',
    borderRadius: 18,
    minWidth: 48,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  badgeText: {
    fontSize: 18,
    fontWeight: '900',
    lineHeight: 22,
  },
  card: {
    alignItems: 'stretch',
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
    height: 202,
    justifyContent: 'flex-start',
    paddingHorizontal: 12,
    paddingTop: 12,
    width: 114,
    ...shadows.card,
  },
  content: {
    gap: 12,
    paddingBottom: 4,
    paddingRight: 18,
  },
  hour: {
    color: colors.textSecondary,
    fontSize: 16,
    lineHeight: 19,
    marginBottom: 8,
    textAlign: 'center',
  },
  pollutantRows: {
    gap: 6,
    marginTop: 10,
  },
  row: {
    alignItems: 'baseline',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  rowLabel: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 15,
    minWidth: 38,
  },
  rowValue: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 15,
    marginLeft: 8,
    minWidth: 36,
    textAlign: 'right',
  },
});

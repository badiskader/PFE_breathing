import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import type { ComponentProps, ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { mockAnalyticsByRange } from '@/mock';
import { colors, shadows } from '@/theme';
import type {
  AnalyticsInsight,
  AnalyticsRange,
  AQICategory,
  AQITrendPoint,
  PollutantKey,
  PollutantRecord,
  SensorComparisonPoint,
} from '@/types';
import { getAQIColor, getAQITextColor } from '@/utils/aqiDisplay';

type MaterialCommunityIconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

const ranges: AnalyticsRange[] = ['24h', '7d', '30d'];
const sensorTabs = ['Centre Ville', 'Bab El Oued', 'El Harrach'];
const pollutantOrder: PollutantKey[] = ['PM25', 'PM10', 'NO2', 'SO2', 'CO', 'O3'];
const pollutantLabels: Record<PollutantKey, string> = {
  CO: 'CO',
  NO2: 'NO2',
  O3: 'O3',
  PM10: 'PM10',
  PM25: 'PM2.5',
  SO2: 'SO2',
};
const pollutantColors: Record<PollutantKey, string> = {
  CO: '#EF4444',
  NO2: '#8859E8',
  O3: '#16B981',
  PM10: '#18B5C6',
  PM25: '#3B82F6',
  SO2: '#F59E0B',
};

export function AnalyticsScreen() {
  const [selectedRange, setSelectedRange] = useState<AnalyticsRange>('24h');
  const [selectedSensor, setSelectedSensor] = useState('Centre Ville');
  const analytics = mockAnalyticsByRange[selectedRange];
  const comparison = useMemo(
    () => [
      analytics.sensorComparison.sensors[0],
      { aqi: 78, name: 'Forecast Peak', sensor_id: 'AQ_FORECAST_PEAK' },
      analytics.sensorComparison.sensors[1],
      analytics.sensorComparison.sensors[2],
    ],
    [analytics.sensorComparison.sensors],
  );

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        <View style={styles.header}>
          <View style={styles.headerBrand}>
            <LinearGradient
              colors={[colors.primaryBlue, colors.secondaryCyan]}
              end={{ x: 1, y: 1 }}
              start={{ x: 0, y: 0 }}
              style={styles.logo}
            >
              <Text style={styles.logoText}>AQ</Text>
            </LinearGradient>
            <Text style={styles.headerTitle}>Analytics</Text>
          </View>
          <View style={styles.bellWrap}>
            <Ionicons color={colors.textSecondary} name="notifications-outline" size={31} />
            <View style={styles.notificationDot} />
          </View>
        </View>

        <View style={styles.rangeControl}>
          {ranges.map((range) => {
            const selected = selectedRange === range;

            return (
              <Pressable
                key={range}
                accessibilityRole="button"
                onPress={() => setSelectedRange(range)}
                style={[styles.rangeOption, selected && styles.rangeOptionSelected]}
              >
                <Text style={[styles.rangeText, selected && styles.rangeTextSelected]}>{range}</Text>
              </Pressable>
            );
          })}
        </View>

        <AnalyticsCard style={styles.trendCard}>
          <Text style={styles.cardTitle}>AQI Trend</Text>
          <View style={styles.sensorTabs}>
            {sensorTabs.map((sensor) => {
              const selected = selectedSensor === sensor;

              return (
                <Pressable
                  key={sensor}
                  onPress={() => setSelectedSensor(sensor)}
                  style={[styles.sensorChip, selected && styles.sensorChipSelected]}
                >
                  <Text style={[styles.sensorChipText, selected && styles.sensorChipTextSelected]}>
                    {sensor}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <TrendChart points={analytics.trend.points} />
          <View style={styles.summaryRow}>
            <SummaryTile label="Avg AQI" tone="softYellow" value={analytics.trend.avg_aqi} />
            <SummaryTile label="Peak AQI" tone="softOrange" value={analytics.trend.peak_aqi} />
            <SummaryTile label="Worst day" tone="softOrange" value={shortWorstDay(analytics.trend.worst_day)} />
          </View>
        </AnalyticsCard>

        <AnalyticsCard>
          <Text style={styles.cardTitle}>Pollutants</Text>
          <PollutantBars bars={analytics.pollutantBars} />
          <PollutantLegend />
        </AnalyticsCard>

        <AnalyticsCard>
          <Text style={styles.cardTitle}>Sensor Comparison</Text>
          <SensorComparison sensors={comparison} />
        </AnalyticsCard>

        <AnalyticsCard>
          <Text style={styles.cardTitle}>Insights</Text>
          <InsightList insights={analytics.insights} />
        </AnalyticsCard>
      </ScrollView>
    </SafeAreaView>
  );
}

function AnalyticsCard({
  children,
  style,
}: {
  children: ReactNode;
  style?: object;
}) {
  return <View style={[styles.card, style]}>{children}</View>;
}

function TrendChart({ points }: { points: AQITrendPoint[] }) {
  const width = 322;
  const height = 116;
  const chartPoints = points.map((point, index) => {
    const maxAQI = 100;
    const x = (index / (points.length - 1)) * width;
    const y = height - (point.aqi / maxAQI) * (height - 18) - 8;

    return { ...point, x, y };
  });

  return (
    <View style={styles.chartWrap}>
      <View style={styles.chartGrid}>
        <View style={[styles.gridLine, { top: 0 }]} />
        <View style={[styles.gridLine, { top: 39 }]} />
        <View style={[styles.gridLine, { top: 78 }]} />
        <LinearGradient
          colors={['rgba(59, 130, 246, 0.26)', 'rgba(59, 130, 246, 0.02)']}
          style={styles.chartAreaFill}
        />
        {chartPoints.slice(0, -1).map((point, index) => {
          const nextPoint = chartPoints[index + 1];
          const dx = nextPoint.x - point.x;
          const dy = nextPoint.y - point.y;
          const length = Math.sqrt(dx * dx + dy * dy);
          const angle = `${Math.atan2(dy, dx)}rad`;

          return (
            <View
              key={`${point.timestamp}-${nextPoint.timestamp}`}
              style={[
                styles.chartSegment,
                {
                  left: point.x,
                  top: point.y,
                  transform: [{ rotate: angle }],
                  width: length,
                },
              ]}
            />
          );
        })}
        {chartPoints.map((point, index) => (
          <View
            key={point.timestamp}
            style={[
              styles.chartDot,
              {
                backgroundColor: pointColor(index),
                left: point.x - 5,
                top: point.y - 5,
              },
            ]}
          />
        ))}
      </View>
      <View style={styles.chartAxis}>
        <Text style={styles.axisText}>0h</Text>
        <Text style={styles.axisText}>6h</Text>
        <Text style={styles.axisText}>12h</Text>
        <Text style={styles.axisText}>18h</Text>
      </View>
    </View>
  );
}

function SummaryTile({ label, tone, value }: { label: string; tone: 'softYellow' | 'softOrange'; value: number | string }) {
  return (
    <View style={[styles.summaryTile, tone === 'softOrange' ? styles.summaryOrange : styles.summaryYellow]}>
      <Text style={styles.summaryValue}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

function PollutantBars({ bars }: { bars: Array<{ label: string; values: PollutantRecord }> }) {
  const displayBars = [{ label: 'PM2.5', values: bars[0].values }, ...bars];

  return (
    <View style={styles.pollutantBars}>
      {displayBars.map((bar) => (
        <View key={bar.label} style={styles.pollutantBarRow}>
          <Text style={styles.pollutantRowLabel}>{bar.label}</Text>
          <View style={styles.stackedTrack}>
            {pollutantOrder.map((pollutant) => (
              <View
                key={`${bar.label}-${pollutant}`}
                style={[
                  styles.stackedSegment,
                  {
                    backgroundColor: pollutantColors[pollutant],
                    flex: bar.values[pollutant],
                  },
                ]}
              />
            ))}
          </View>
        </View>
      ))}
    </View>
  );
}

function PollutantLegend() {
  return (
    <View style={styles.legend}>
      {pollutantOrder.map((pollutant) => (
        <View key={pollutant} style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: pollutantColors[pollutant] }]} />
          <Text style={styles.legendText}>{pollutantLabels[pollutant]}</Text>
        </View>
      ))}
    </View>
  );
}

function SensorComparison({ sensors }: { sensors: SensorComparisonPoint[] }) {
  const maxAQI = Math.max(...sensors.map((sensor) => sensor.aqi), 120);

  return (
    <View style={styles.comparisonList}>
      {sensors.map((sensor) => {
        const category = categoryFromAQI(sensor.aqi);
        const color = getAQIColor(category);
        const textColor = getAQITextColor(category);

        return (
          <View key={sensor.sensor_id} style={styles.comparisonTrack}>
            <View
              style={[
                styles.comparisonFill,
                {
                  backgroundColor: color,
                  width: `${Math.max(13, (sensor.aqi / maxAQI) * 100)}%`,
                },
              ]}
            >
              <Text style={[styles.comparisonValue, { color: textColor }]}>{sensor.aqi}</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

function InsightList({ insights }: { insights: AnalyticsInsight[] }) {
  const icons: MaterialCommunityIconName[] = [
    'weather-sunset-up',
    'weather-partly-cloudy',
    'chart-line-variant',
  ];

  return (
    <View style={styles.insightList}>
      {insights.map((insight, index) => (
        <View key={insight.insight_id} style={styles.insightRow}>
          <MaterialCommunityIcons color="#050505" name={icons[index] ?? 'chart-line'} size={28} />
          <Text style={styles.insightText}>{insight.title}</Text>
        </View>
      ))}
    </View>
  );
}

function categoryFromAQI(value: number): AQICategory {
  if (value <= 50) return 'Good';
  if (value <= 100) return 'Moderate';
  if (value <= 150) return 'Unhealthy for Sensitive Groups';
  if (value <= 200) return 'Unhealthy';
  if (value <= 300) return 'Very Unhealthy';
  return 'Hazardous';
}

function pointColor(index: number) {
  if (index === 2) return colors.unhealthyOrange;
  if ([0, 1, 3, 4, 5, 9].includes(index)) return colors.moderateYellow;
  return colors.goodGreen;
}

function shortWorstDay(day: string) {
  const frenchDays: Record<string, string> = {
    Friday: 'Ven',
    Monday: 'Lun',
    Saturday: 'Sam',
    Sunday: 'Dim',
    Thursday: 'Jeu',
    Tuesday: 'Mar',
    Wednesday: 'Mer',
  };

  return frenchDays[day] ?? day;
}

const styles = StyleSheet.create({
  axisText: {
    color: colors.textMuted,
    fontSize: 15,
    lineHeight: 18,
  },
  bellWrap: {
    position: 'relative',
  },
  card: {
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 22,
    borderWidth: StyleSheet.hairlineWidth,
    marginHorizontal: 16,
    paddingHorizontal: 12,
    paddingVertical: 20,
    ...shadows.card,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 27,
  },
  chartAreaFill: {
    bottom: 0,
    height: 88,
    left: 0,
    opacity: 0.85,
    position: 'absolute',
    width: '53%',
  },
  chartAxis: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 5,
  },
  chartDot: {
    borderColor: colors.white,
    borderRadius: 6,
    borderWidth: 2,
    height: 12,
    position: 'absolute',
    width: 12,
    zIndex: 2,
  },
  chartGrid: {
    height: 116,
    marginTop: 14,
    position: 'relative',
  },
  chartSegment: {
    backgroundColor: colors.primaryBlue,
    borderRadius: 2,
    height: 3,
    position: 'absolute',
    transformOrigin: 'left center',
    zIndex: 1,
  },
  chartWrap: {
    marginTop: 10,
  },
  comparisonFill: {
    alignItems: 'flex-end',
    borderRadius: 16,
    height: 30,
    justifyContent: 'center',
    minWidth: 48,
    paddingRight: 10,
  },
  comparisonList: {
    gap: 13,
    marginLeft: 110,
    marginTop: 28,
  },
  comparisonTrack: {
    backgroundColor: '#EFF1F5',
    borderRadius: 16,
    height: 30,
    overflow: 'hidden',
  },
  comparisonValue: {
    fontSize: 16,
    fontWeight: '900',
    lineHeight: 20,
  },
  gridLine: {
    backgroundColor: '#E8EDF3',
    height: 1,
    left: 0,
    position: 'absolute',
    right: 0,
  },
  header: {
    alignItems: 'center',
    backgroundColor: colors.white,
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingBottom: 14,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  headerBrand: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 14,
  },
  headerTitle: {
    color: colors.textPrimary,
    fontSize: 23,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 28,
  },
  insightList: {
    gap: 12,
    marginTop: 18,
  },
  insightRow: {
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderRadius: 14,
    flexDirection: 'row',
    gap: 12,
    minHeight: 61,
    paddingHorizontal: 14,
  },
  insightText: {
    color: '#4A5568',
    flex: 1,
    fontSize: 16,
    lineHeight: 22,
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 11,
  },
  legendDot: {
    borderRadius: 6,
    height: 12,
    width: 12,
  },
  legendItem: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 5,
  },
  legendText: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 18,
  },
  logo: {
    alignItems: 'center',
    borderRadius: 14,
    height: 46,
    justifyContent: 'center',
    width: 46,
  },
  logoText: {
    color: colors.white,
    fontSize: 19,
    fontWeight: '900',
  },
  notificationDot: {
    backgroundColor: '#FF3345',
    borderColor: colors.white,
    borderRadius: 7,
    borderWidth: 2,
    height: 13,
    position: 'absolute',
    right: -1,
    top: 0,
    width: 13,
  },
  pollutantBars: {
    gap: 10,
    marginTop: 24,
  },
  pollutantBarRow: {
    alignItems: 'center',
    flexDirection: 'row',
  },
  pollutantRowLabel: {
    color: colors.textMuted,
    fontSize: 15,
    lineHeight: 18,
    width: 55,
  },
  rangeControl: {
    alignItems: 'center',
    backgroundColor: '#EEF0F4',
    borderRadius: 16,
    flexDirection: 'row',
    height: 58,
    marginHorizontal: 16,
    marginTop: 18,
    padding: 2,
  },
  rangeOption: {
    alignItems: 'center',
    borderRadius: 14,
    flex: 1,
    height: 54,
    justifyContent: 'center',
  },
  rangeOptionSelected: {
    backgroundColor: colors.white,
    ...shadows.card,
  },
  rangeText: {
    color: colors.textSecondary,
    fontSize: 19,
    fontWeight: '800',
    lineHeight: 24,
  },
  rangeTextSelected: {
    color: '#243043',
  },
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  scrollContent: {
    gap: 16,
    paddingBottom: 84,
  },
  sensorChip: {
    backgroundColor: '#F1F3F6',
    borderRadius: 15,
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  sensorChipSelected: {
    backgroundColor: '#DDEEFF',
  },
  sensorChipText: {
    color: colors.textSecondary,
    fontSize: 16,
    lineHeight: 21,
  },
  sensorChipTextSelected: {
    color: '#0057FF',
  },
  sensorTabs: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 16,
  },
  stackedSegment: {
    height: '100%',
  },
  stackedTrack: {
    backgroundColor: '#EFF1F5',
    borderRadius: 12,
    flex: 1,
    flexDirection: 'row',
    height: 24,
    overflow: 'hidden',
  },
  summaryLabel: {
    color: '#A17642',
    fontSize: 17,
    lineHeight: 22,
    textAlign: 'center',
  },
  summaryOrange: {
    backgroundColor: '#FFF0E7',
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 14,
  },
  summaryTile: {
    alignItems: 'center',
    borderRadius: 14,
    flex: 1,
    height: 72,
    justifyContent: 'center',
  },
  summaryValue: {
    color: '#815006',
    fontSize: 22,
    fontWeight: '900',
    lineHeight: 26,
  },
  summaryYellow: {
    backgroundColor: '#FFF8DF',
  },
  trendCard: {
    marginTop: 8,
  },
});

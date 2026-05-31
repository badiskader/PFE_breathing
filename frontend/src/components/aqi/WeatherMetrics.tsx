import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, shadows } from '@/theme';
import type { WeatherSnapshot } from '@/types';

type WeatherMetricsProps = {
  weather: WeatherSnapshot;
};

type WeatherMetric = {
  icon: ComponentProps<typeof Ionicons>['name'];
  label: string;
  value: string;
};

export function WeatherMetrics({ weather }: WeatherMetricsProps) {
  const metrics: WeatherMetric[] = [
    {
      icon: 'sunny-outline',
      label: 'Temp',
      value: `${Math.round(weather.temperature_2m)}°C`,
    },
    {
      icon: 'compass-outline',
      label: 'Wind',
      value: `${Math.round(weather.wind_speed_10m)} km/h`,
    },
    {
      icon: 'water',
      label: 'Humidity',
      value: `${Math.round(weather.relative_humidity_2m)}%`,
    },
  ];

  return (
    <View style={styles.card}>
      {metrics.map((metric, index) => (
        <View key={metric.label} style={styles.metricWrap}>
          <View style={styles.metric}>
            <Ionicons color="#050505" name={metric.icon} size={29} />
            <Text style={styles.value}>{metric.value}</Text>
            <Text style={styles.label}>{metric.label}</Text>
          </View>
          {index < metrics.length - 1 ? <View style={styles.separator} /> : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    alignItems: 'center',
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 22,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    height: 90,
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    ...shadows.card,
  },
  label: {
    color: colors.textMuted,
    fontSize: 17,
    lineHeight: 21,
  },
  metric: {
    alignItems: 'center',
    flex: 1,
    gap: 4,
    justifyContent: 'center',
  },
  metricWrap: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    height: '72%',
  },
  separator: {
    backgroundColor: colors.border,
    height: '100%',
    width: StyleSheet.hairlineWidth,
  },
  value: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: '800',
    lineHeight: 24,
    marginTop: 4,
  },
});

import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useMemo, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AirQualityMap } from '@/components/map/AirQualityMap';
import { useSensorsAQI } from '@/hooks/useSensorsAQI';
import { colors, shadows } from '@/theme';
import type { AQICategory, PollutantKey, SensorAQI } from '@/types';
import { getAQIColor, getAQISubtleTextColor, getAQITextColor } from '@/utils/aqiDisplay';
import { formatCompactPollutantValue } from '@/utils/pollutantFormat';

const displayCoordinates: Record<string, string> = {
  AQ_CST_02: '36.7538\u00b0 N, 3.0588\u00b0 E',
};

const pollutantTiles: Array<{ key: PollutantKey; label: string }> = [
  { key: 'PM25', label: 'PM2.5' },
  { key: 'PM10', label: 'PM10' },
  { key: 'NO2', label: 'NO2' },
  { key: 'SO2', label: 'SO2' },
  { key: 'CO', label: 'CO' },
  { key: 'O3', label: 'O3' },
];

const mapForecastValues = [22, 28, 35, 51, 63, 78, 95, 105];

export function MapScreen() {
  const sensorsQuery = useSensorsAQI();
  const [selectedSensorId, setSelectedSensorId] = useState<string | null>(null);
  const sensors = sensorsQuery.data.sensors;
  const selectedSensor = selectedSensorId
    ? sensors.find((sensor) => sensor.sensor_id === selectedSensorId) ?? null
    : null;
  const forecast = useMemo(
    () => (selectedSensor ? buildMapForecast(selectedSensor) : []),
    [selectedSensor],
  );

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <View style={styles.container}>
        <AirQualityMap
          sensors={sensors}
          selectedSensorId={selectedSensorId}
          onMapPress={() => setSelectedSensorId(null)}
          onSelectSensor={setSelectedSensorId}
        />

        <View pointerEvents="box-none" style={styles.overlay}>
          <View style={styles.searchBar}>
            <Ionicons color={colors.textMuted} name="search-outline" size={25} />
            <Text style={styles.searchPlaceholder}>Search location...</Text>
            <View style={styles.layersPill}>
              <Text style={styles.layersText}>Layers</Text>
            </View>
          </View>

          {!selectedSensor ? (
            <View style={styles.tapHint}>
              <Text style={styles.tapHintText}>Tap a sensor to view details</Text>
            </View>
          ) : null}

          {selectedSensor ? (
            <View style={styles.bottomSheetWrap}>
              <StationSheet
                forecast={forecast}
                sensor={selectedSensor}
                onClose={() => setSelectedSensorId(null)}
              />
            </View>
          ) : null}
        </View>
      </View>
    </SafeAreaView>
  );
}

function StationSheet({
  forecast,
  onClose,
  sensor,
}: {
  forecast: MapForecastItem[];
  onClose: () => void;
  sensor: SensorAQI;
}) {
  const categoryColor = getAQIColor(sensor.aqi_category);
  const categoryTextColor = getAQITextColor(sensor.aqi_category);
  const subtleTextColor = getAQISubtleTextColor(sensor.aqi_category);
  const coordinates =
    displayCoordinates[sensor.sensor_id] ??
    `${sensor.latitude?.toFixed(4) ?? '36.7538'}\u00b0 N, ${sensor.longitude?.toFixed(4) ?? '3.0588'}\u00b0 E`;
  const pollutants = sensor.pollutants ?? sensor.sub_indices;

  return (
    <View style={styles.sheet}>
      <Pressable accessibilityRole="button" onPress={onClose} style={styles.sheetHandleHitbox}>
        <View style={styles.sheetHandle} />
      </Pressable>

      <View style={styles.sheetTitleRow}>
        <View style={styles.sheetTitleText}>
          <Text style={styles.stationTitle}>Station {sensor.name}</Text>
          <Text style={styles.coordinates}>{coordinates}</Text>
        </View>
        <View style={[styles.categoryPill, { backgroundColor: colorWithOpacity(categoryColor, 0.24) }]}>
          <Text style={[styles.categoryPillText, { color: categoryTextColor }]}>
            {formatCategoryPill(sensor.aqi_category)}
          </Text>
        </View>
      </View>

      <View style={[styles.aqiPanel, { backgroundColor: colorWithOpacity(categoryColor, 0.18) }]}>
        <Text style={[styles.sheetAQI, { color: categoryTextColor }]}>{sensor.aqi_score}</Text>
        <View style={styles.sheetAQICopy}>
          <Text style={[styles.sheetCategory, { color: categoryTextColor }]}>{sensor.aqi_category}</Text>
          <Text style={styles.dominantText}>Dominant: PM2.5</Text>
        </View>
        <MaterialCommunityIcons color="#050505" name={moodIcon(sensor.aqi_category)} size={55} />
      </View>

      <View style={styles.pollutantGrid}>
        {pollutantTiles.map((pollutant) => (
          <View key={pollutant.key} style={styles.pollutantTile}>
            <Text style={styles.pollutantValue}>{formatCompactPollutantValue(pollutants[pollutant.key])}</Text>
            <Text style={styles.pollutantLabel}>{pollutant.label}</Text>
          </View>
        ))}
      </View>

      <View style={styles.forecastBlock}>
        <Text style={styles.forecastTitle}>12h Forecast</Text>
        <View style={styles.forecastRow}>
          {forecast.map((item) => {
            const color = getAQIColor(item.category);
            const textColor = getAQITextColor(item.category);

            return (
              <View key={item.hour} style={styles.forecastItem}>
                <Text style={styles.forecastHour}>{item.hour}</Text>
                <View style={[styles.forecastBadge, { backgroundColor: color }]}>
                  <Text style={[styles.forecastValue, { color: textColor }]}>{item.value}</Text>
                </View>
              </View>
            );
          })}
        </View>
      </View>
      <View style={[styles.sheetAccentLine, { backgroundColor: subtleTextColor }]} />
    </View>
  );
}

type MapForecastItem = {
  category: AQICategory;
  hour: string;
  value: number;
};

function buildMapForecast(sensor: SensorAQI): MapForecastItem[] {
  const start = new Date(sensor.timestamp);

  return mapForecastValues.map((value, index) => {
    const hourDate = new Date(start);
    hourDate.setUTCHours(start.getUTCHours() + index);

    return {
      category: categoryFromAQI(value),
      hour: formatMapHour(hourDate),
      value,
    };
  });
}

function formatMapHour(date: Date) {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    hour12: true,
    timeZone: 'UTC',
  })
    .format(date)
    .replace(' PM', 'P')
    .replace(' AM', 'A');
}

function categoryFromAQI(value: number): AQICategory {
  if (value <= 50) return 'Good';
  if (value <= 100) return 'Moderate';
  if (value <= 150) return 'Unhealthy for Sensitive Groups';
  if (value <= 200) return 'Unhealthy';
  if (value <= 300) return 'Very Unhealthy';
  return 'Hazardous';
}

function formatCategoryPill(category: AQICategory) {
  if (category === 'Unhealthy for Sensitive Groups') {
    return 'SENSITIVE';
  }

  return category.toUpperCase();
}

function moodIcon(category: AQICategory) {
  if (category === 'Good') return 'emoticon-happy-outline';
  if (category === 'Moderate') return 'emoticon-neutral-outline';
  return 'emoticon-sad-outline';
}

function colorWithOpacity(hexColor: string, opacity: number) {
  const hex = hexColor.replace('#', '');
  const red = Number.parseInt(hex.slice(0, 2), 16);
  const green = Number.parseInt(hex.slice(2, 4), 16);
  const blue = Number.parseInt(hex.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
}

const styles = StyleSheet.create({
  aqiPanel: {
    alignItems: 'center',
    borderRadius: 18,
    flexDirection: 'row',
    height: 78,
    marginTop: 12,
    paddingHorizontal: 22,
  },
  bottomSheetWrap: {
    bottom: 0,
    left: 0,
    position: 'absolute',
    right: 0,
  },
  categoryPill: {
    alignItems: 'center',
    borderRadius: 17,
    justifyContent: 'center',
    minWidth: 84,
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  categoryPillText: {
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0,
  },
  container: {
    backgroundColor: '#D7EBC8',
    flex: 1,
    position: 'relative',
  },
  coordinates: {
    color: colors.textMuted,
    fontSize: 19,
    lineHeight: 24,
    marginTop: 6,
  },
  dominantText: {
    color: colors.textSecondary,
    fontSize: 18,
    lineHeight: 23,
  },
  forecastBadge: {
    alignItems: 'center',
    alignSelf: 'center',
    borderRadius: 18,
    height: 26,
    justifyContent: 'center',
    minWidth: 38,
    paddingHorizontal: 8,
  },
  forecastBlock: {
    gap: 7,
    marginTop: 9,
  },
  forecastHour: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 17,
    textAlign: 'center',
  },
  forecastItem: {
    alignItems: 'center',
    gap: 4,
    width: 39,
  },
  forecastRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  forecastTitle: {
    color: colors.textSecondary,
    fontSize: 18,
    fontWeight: '600',
    lineHeight: 24,
  },
  forecastValue: {
    fontSize: 15,
    fontWeight: '900',
    lineHeight: 19,
  },
  layersPill: {
    backgroundColor: colors.mutedSurface,
    borderRadius: 16,
    paddingHorizontal: 13,
    paddingVertical: 7,
  },
  layersText: {
    color: colors.textMuted,
    fontSize: 18,
    lineHeight: 20,
  },
  overlay: {
    bottom: 0,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  pollutantGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
    marginTop: 12,
  },
  pollutantLabel: {
    color: '#5B7F35',
    fontSize: 16,
    lineHeight: 20,
    textAlign: 'center',
  },
  pollutantTile: {
    alignItems: 'center',
    backgroundColor: '#E7F7D5',
    borderRadius: 14,
    height: 49,
    justifyContent: 'center',
    width: '31.75%',
  },
  pollutantValue: {
    color: '#2C640B',
    fontSize: 17,
    fontWeight: '900',
    lineHeight: 21,
  },
  safeArea: {
    backgroundColor: '#D7EBC8',
    flex: 1,
  },
  searchBar: {
    alignItems: 'center',
    alignSelf: 'center',
    backgroundColor: colors.white,
    borderRadius: 29,
    flexDirection: 'row',
    gap: 12,
    height: 58,
    left: 16,
    paddingLeft: 24,
    paddingRight: 14,
    position: 'absolute',
    right: 16,
    top: Platform.select({ default: 24, web: 42 }),
    ...shadows.soft,
  },
  searchPlaceholder: {
    color: colors.textMuted,
    flex: 1,
    fontSize: 22,
    lineHeight: 27,
  },
  sheet: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    minHeight: 338,
    paddingBottom: 10,
    paddingHorizontal: 16,
    paddingTop: 30,
    position: 'relative',
    ...shadows.soft,
  },
  sheetAccentLine: {
    borderRadius: 2,
    bottom: 0,
    height: 4,
    left: 16,
    opacity: 0,
    position: 'absolute',
    width: 64,
  },
  sheetAQI: {
    fontSize: 45,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 51,
    marginRight: 17,
    minWidth: 58,
  },
  sheetAQICopy: {
    flex: 1,
  },
  sheetCategory: {
    fontSize: 20,
    fontWeight: '800',
    lineHeight: 25,
  },
  sheetHandle: {
    alignSelf: 'center',
    backgroundColor: '#DDE2EA',
    borderRadius: 3,
    height: 6,
    width: 41,
  },
  sheetHandleHitbox: {
    alignItems: 'center',
    height: 22,
    justifyContent: 'center',
    left: 0,
    position: 'absolute',
    right: 0,
    top: 4,
  },
  sheetTitleRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  sheetTitleText: {
    flex: 1,
  },
  stationTitle: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 25,
  },
  tapHint: {
    alignSelf: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.94)',
    borderRadius: 16,
    bottom: 24,
    paddingHorizontal: 16,
    paddingVertical: 9,
    position: 'absolute',
    ...shadows.card,
  },
  tapHintText: {
    color: colors.textSecondary,
    fontSize: 14,
    fontWeight: '700',
  },
});

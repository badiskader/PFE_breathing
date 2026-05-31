import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme';
import type { SensorAQI } from '@/types';
import { getAQIColor, getAQITextColor } from '@/utils/aqiDisplay';

type AirQualityMapProps = {
  onMapPress: () => void;
  onSelectSensor: (sensorId: string) => void;
  selectedSensorId: string | null;
  sensors: SensorAQI[];
};

const markerPositions = {
  AQ_CST_01: { left: '6%', top: '38%' },
  AQ_CST_02: { left: '33%', top: '63%' },
  AQ_CST_03: { left: '66%', top: '47%' },
} as const;

export function AirQualityMap({
  onMapPress,
  onSelectSensor,
  selectedSensorId,
  sensors,
}: AirQualityMapProps) {
  return (
    <Pressable onPress={onMapPress} style={StyleSheet.absoluteFill}>
      <MapTexture />
      {sensors.map((sensor) => (
        <StationMarker
          key={sensor.sensor_id}
          selected={sensor.sensor_id === selectedSensorId}
          sensor={sensor}
          onPress={() => onSelectSensor(sensor.sensor_id)}
        />
      ))}
    </Pressable>
  );
}

function MapTexture() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={[styles.mapBand, styles.mapBandLeft]} />
      <View style={[styles.mapBand, styles.mapBandCenter]} />
      <View style={[styles.mapBand, styles.mapBandRight]} />
      <View style={[styles.mapRoad, styles.verticalRoadOne]} />
      <View style={[styles.mapRoad, styles.verticalRoadTwo]} />
      <View style={[styles.mapRoad, styles.horizontalRoad]} />
      <View style={[styles.mapBlock, styles.blockOne]} />
      <View style={[styles.mapBlock, styles.blockTwo]} />
      <View style={[styles.mapBlock, styles.blockThree]} />
    </View>
  );
}

function StationMarker({
  onPress,
  selected,
  sensor,
}: {
  onPress: () => void;
  selected: boolean;
  sensor: SensorAQI;
}) {
  const color = getAQIColor(sensor.aqi_category);
  const textColor = getAQITextColor(sensor.aqi_category);
  const position = markerPositions[sensor.sensor_id as keyof typeof markerPositions] ?? markerPositions.AQ_CST_01;

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.markerWrap, position, selected && styles.selectedMarker]}
    >
      <View
        style={[
          styles.markerAura,
          {
            backgroundColor: colorWithOpacity(color, 0.16),
            borderColor: colorWithOpacity(color, 0.55),
          },
        ]}
      />
      <View style={styles.pinWrap}>
        <View style={[styles.pinBubble, { backgroundColor: color }]}>
          <Text style={[styles.pinText, { color: textColor }]}>{sensor.aqi_score}</Text>
        </View>
        <View style={[styles.pinPoint, { backgroundColor: color }]} />
      </View>
    </Pressable>
  );
}

function colorWithOpacity(hexColor: string, opacity: number) {
  const hex = hexColor.replace('#', '');
  const red = Number.parseInt(hex.slice(0, 2), 16);
  const green = Number.parseInt(hex.slice(2, 4), 16);
  const blue = Number.parseInt(hex.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
}

const styles = StyleSheet.create({
  blockOne: {
    bottom: 86,
    height: 52,
    left: '8%',
    width: '18%',
  },
  blockThree: {
    bottom: 92,
    height: 52,
    right: '8%',
    width: '21%',
  },
  blockTwo: {
    bottom: 86,
    height: 58,
    left: '41%',
    width: '16%',
  },
  horizontalRoad: {
    bottom: 155,
    height: 3,
    left: '-8%',
    right: '-8%',
    transform: [{ rotate: '-1.6deg' }],
  },
  mapBand: {
    backgroundColor: 'rgba(242, 250, 235, 0.22)',
    bottom: 0,
    position: 'absolute',
    top: 0,
    width: '19%',
  },
  mapBandCenter: {
    left: '42%',
  },
  mapBandLeft: {
    left: '17%',
  },
  mapBandRight: {
    right: '22%',
  },
  mapBlock: {
    backgroundColor: 'rgba(175, 201, 157, 0.12)',
    borderColor: 'rgba(139, 174, 122, 0.12)',
    borderWidth: 1,
    position: 'absolute',
  },
  mapRoad: {
    backgroundColor: 'rgba(255, 255, 255, 0.54)',
    position: 'absolute',
  },
  markerAura: {
    borderRadius: 56,
    borderWidth: 1,
    height: 112,
    left: 3,
    position: 'absolute',
    top: 25,
    width: 112,
  },
  markerWrap: {
    alignItems: 'center',
    height: 142,
    justifyContent: 'flex-start',
    position: 'absolute',
    width: 118,
  },
  pinBubble: {
    alignItems: 'center',
    borderRadius: 15,
    height: 56,
    justifyContent: 'center',
    width: 48,
  },
  pinPoint: {
    height: 17,
    marginTop: -11,
    transform: [{ rotate: '45deg' }],
    width: 17,
  },
  pinText: {
    fontSize: 18,
    fontWeight: '900',
  },
  pinWrap: {
    alignItems: 'center',
    position: 'absolute',
    top: 0,
  },
  selectedMarker: {
    zIndex: 2,
  },
  verticalRoadOne: {
    bottom: 0,
    left: '30.5%',
    top: 0,
    width: 2,
  },
  verticalRoadTwo: {
    bottom: 0,
    right: '33%',
    top: 0,
    width: 2,
  },
});

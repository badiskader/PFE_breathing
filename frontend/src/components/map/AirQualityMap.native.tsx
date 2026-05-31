import { Fragment } from 'react';
import MapView, { Circle, Marker, PROVIDER_GOOGLE, type MapStyleElement } from 'react-native-maps';
import { StyleSheet, Text, View } from 'react-native';

import type { SensorAQI } from '@/types';
import { getAQIColor, getAQITextColor } from '@/utils/aqiDisplay';

type AirQualityMapProps = {
  onMapPress: () => void;
  onSelectSensor: (sensorId: string) => void;
  selectedSensorId: string | null;
  sensors: SensorAQI[];
};

const ALGIERS_REGION = {
  latitude: 36.776,
  latitudeDelta: 0.13,
  longitude: 3.0,
  longitudeDelta: 0.34,
};

export function AirQualityMap({
  onMapPress,
  onSelectSensor,
  selectedSensorId,
  sensors,
}: AirQualityMapProps) {
  return (
    <MapView
      customMapStyle={GOOGLE_MAP_STYLE}
      initialRegion={ALGIERS_REGION}
      loadingEnabled
      onPress={onMapPress}
      provider={PROVIDER_GOOGLE}
      rotateEnabled={false}
      showsBuildings={false}
      showsCompass={false}
      showsPointsOfInterests={false}
      style={StyleSheet.absoluteFill}
      toolbarEnabled={false}
    >
      {sensors.map((sensor) => {
        const coordinate = sensorCoordinate(sensor);
        const color = getAQIColor(sensor.aqi_category);

        return (
          <Fragment key={sensor.sensor_id}>
            <Circle
              center={coordinate}
              fillColor={colorWithOpacity(color, 0.16)}
              radius={950}
              strokeColor={colorWithOpacity(color, 0.55)}
              strokeWidth={1}
            />
            <Marker
              anchor={{ x: 0.5, y: 1 }}
              coordinate={coordinate}
              onPress={() => onSelectSensor(sensor.sensor_id)}
              tracksViewChanges={false}
            >
              <MapPin selected={sensor.sensor_id === selectedSensorId} sensor={sensor} />
            </Marker>
          </Fragment>
        );
      })}
    </MapView>
  );
}

function MapPin({ selected, sensor }: { selected: boolean; sensor: SensorAQI }) {
  const color = getAQIColor(sensor.aqi_category);
  const textColor = getAQITextColor(sensor.aqi_category);

  return (
    <View style={[styles.pinWrap, selected && styles.selectedPin]}>
      <View style={[styles.pinBubble, { backgroundColor: color }]}>
        <Text style={[styles.pinText, { color: textColor }]}>{sensor.aqi_score}</Text>
      </View>
      <View style={[styles.pinPoint, { backgroundColor: color }]} />
    </View>
  );
}

function sensorCoordinate(sensor: SensorAQI) {
  return {
    latitude: sensor.latitude ?? 36.776,
    longitude: sensor.longitude ?? 3,
  };
}

function colorWithOpacity(hexColor: string, opacity: number) {
  const hex = hexColor.replace('#', '');
  const red = Number.parseInt(hex.slice(0, 2), 16);
  const green = Number.parseInt(hex.slice(2, 4), 16);
  const blue = Number.parseInt(hex.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
}

const styles = StyleSheet.create({
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
    transform: [{ scale: 1 }],
  },
  selectedPin: {
    transform: [{ scale: 1.08 }],
  },
});

const GOOGLE_MAP_STYLE: MapStyleElement[] = [
  {
    elementType: 'geometry',
    stylers: [{ color: '#D7EBC8' }],
  },
  {
    elementType: 'labels.icon',
    stylers: [{ visibility: 'off' }],
  },
  {
    elementType: 'labels.text.fill',
    stylers: [{ color: '#7C8B72' }],
  },
  {
    elementType: 'labels.text.stroke',
    stylers: [{ color: '#ECF6E4' }],
  },
  {
    featureType: 'administrative',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#C5DAB7' }],
  },
  {
    featureType: 'landscape.man_made',
    elementType: 'geometry',
    stylers: [{ color: '#CFE6C0' }],
  },
  {
    featureType: 'poi',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#EFF8E9' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#D5E7CB' }],
  },
  {
    featureType: 'road',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'transit',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#C9E7EF' }],
  },
];

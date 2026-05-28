import type { SensorTableEntry } from '@/types';

export const mockSensorTable: Record<string, SensorTableEntry> = {
  AQ_CST_01: {
    sensor_id: 'AQ_CST_01',
    name: 'Centre Ville',
    latitude: 36.764764,
    longitude: 2.844442,
    radius_km: 0.6,
  },
  AQ_CST_02: {
    sensor_id: 'AQ_CST_02',
    name: 'Bab El Oued',
    latitude: 36.803986,
    longitude: 2.894873,
    radius_km: 0.6,
  },
  AQ_CST_03: {
    sensor_id: 'AQ_CST_03',
    name: 'El Harrach',
    latitude: 36.741991,
    longitude: 3.145934,
    radius_km: 0.6,
  },
};

export const mockSensorIds = Object.keys(mockSensorTable);

export const mockSensorEntries = Object.values(mockSensorTable);

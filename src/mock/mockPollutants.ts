import type { PollutantRecord } from '@/types';

export const mockPollutantsBySensorId: Record<string, PollutantRecord> = {
  AQ_CST_01: {
    PM25: 4,
    PM10: 8,
    NO2: 5,
    SO2: 2,
    CO: 120,
    O3: 31,
  },
  AQ_CST_02: {
    PM25: 22,
    PM10: 38,
    NO2: 15,
    SO2: 8,
    CO: 45,
    O3: 31,
  },
  AQ_CST_03: {
    PM25: 39,
    PM10: 56,
    NO2: 66,
    SO2: 15,
    CO: 352,
    O3: 56,
  },
};

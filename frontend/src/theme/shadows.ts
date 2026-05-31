import { Platform } from 'react-native';

export const shadows = {
  card: Platform.select({
    ios: {
      shadowColor: '#172033',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.08,
      shadowRadius: 12,
    },
    android: {
      elevation: 2,
    },
    default: {},
  }),
  soft: Platform.select({
    ios: {
      shadowColor: '#172033',
      shadowOffset: { width: 0, height: 6 },
      shadowOpacity: 0.12,
      shadowRadius: 18,
    },
    android: {
      elevation: 4,
    },
    default: {},
  }),
} as const;

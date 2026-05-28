import { DefaultTheme, type Theme } from '@react-navigation/native';

import { colors } from '@/theme';

export const navigationTheme: Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.primaryBlue,
    background: colors.background,
    card: colors.card,
    text: colors.textPrimary,
    border: colors.border,
    notification: colors.dangerousRed,
  },
};

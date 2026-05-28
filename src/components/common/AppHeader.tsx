import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';

type AppHeaderProps = {
  title: string;
  subtitle?: string;
};

export function AppHeader({ title, subtitle }: AppHeaderProps) {
  return (
    <View style={styles.container}>
      <LinearGradient
        colors={[colors.primaryBlue, colors.secondaryCyan]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.logo}
      >
        <Text style={styles.logoText}>AQ</Text>
      </LinearGradient>
      <View style={styles.copy}>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.md,
  },
  logo: {
    alignItems: 'center',
    borderRadius: 14,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  logoText: {
    color: colors.white,
    fontSize: 18,
    fontWeight: '800',
  },
  copy: {
    flex: 1,
  },
  title: {
    color: colors.textPrimary,
    fontSize: typography.screenTitle.fontSize,
    fontWeight: '800',
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: typography.meta.fontSize,
    marginTop: 2,
  },
});

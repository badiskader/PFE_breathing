import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';

type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  title: string;
};

export function ErrorState({ message, onRetry, retryLabel, title }: ErrorStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.message}>{message}</Text>
      {onRetry && retryLabel ? (
        <Pressable accessibilityRole="button" onPress={onRetry} style={styles.retry}>
          <Text style={styles.retryText}>{retryLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.errorSurface,
    borderColor: colors.dangerousRed,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.sm,
    padding: spacing.lg,
  },
  title: {
    color: colors.textPrimary,
    fontSize: typography.sectionTitle.fontSize,
    fontWeight: '700',
  },
  message: {
    color: colors.textSecondary,
    fontSize: typography.bodySmall.fontSize,
    lineHeight: typography.bodySmall.lineHeight,
  },
  retry: {
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
  },
  retryText: {
    color: colors.primaryBlue,
    fontSize: typography.bodySmall.fontSize,
    fontWeight: '700',
  },
});

import { LinearGradient } from 'expo-linear-gradient';
import type { PropsWithChildren } from 'react';
import { Pressable, StyleSheet, Text, type GestureResponderEvent } from 'react-native';

import { colors, spacing, typography } from '@/theme';

type GradientButtonProps = PropsWithChildren<{
  label: string;
  disabled?: boolean;
  onPress?: (event: GestureResponderEvent) => void;
}>;

export function GradientButton({ disabled, label, onPress }: GradientButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.pressable, pressed && !disabled ? styles.pressed : null]}
    >
      <LinearGradient
        colors={
          disabled
            ? [colors.mutedSurface, colors.mutedSurface]
            : [colors.primaryBlue, colors.secondaryCyan]
        }
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradient}
      >
        <Text style={[styles.label, disabled ? styles.disabledLabel : null]}>{label}</Text>
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressable: {
    borderRadius: 8,
  },
  pressed: {
    opacity: 0.88,
  },
  gradient: {
    alignItems: 'center',
    borderRadius: 8,
    minHeight: 52,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  label: {
    color: colors.white,
    fontSize: typography.body.fontSize,
    fontWeight: '700',
  },
  disabledLabel: {
    color: colors.textSecondary,
  },
});

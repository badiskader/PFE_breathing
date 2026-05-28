import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppHeader } from '@/components/common/AppHeader';
import { Card } from '@/components/common/Card';
import { Screen } from '@/components/common/Screen';
import { colors, spacing, typography } from '@/theme';

export type PlaceholderAction = {
  label: string;
  onPress: () => void;
  tone?: 'primary' | 'secondary';
};

type PlaceholderScreenProps = {
  actions?: PlaceholderAction[];
  body: string;
  eyebrow?: string;
  title: string;
};

export function PlaceholderScreen({ actions = [], body, eyebrow, title }: PlaceholderScreenProps) {
  return (
    <Screen contentContainerStyle={styles.content}>
      <AppHeader subtitle={eyebrow} title={title} />
      <Card style={styles.card}>
        <Text style={styles.body}>{body}</Text>
        {actions.length > 0 ? (
          <View style={styles.actions}>
            {actions.map((action) => (
              <Pressable
                accessibilityRole="button"
                key={action.label}
                onPress={action.onPress}
                style={[
                  styles.action,
                  action.tone === 'secondary' ? styles.secondaryAction : styles.primaryAction,
                ]}
              >
                <Text
                  style={[
                    styles.actionText,
                    action.tone === 'secondary'
                      ? styles.secondaryActionText
                      : styles.primaryActionText,
                  ]}
                >
                  {action.label}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  action: {
    alignItems: 'center',
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: spacing.lg,
  },
  actions: {
    gap: spacing.sm,
  },
  actionText: {
    fontSize: typography.bodySmall.fontSize,
    fontWeight: '700',
  },
  body: {
    color: colors.textSecondary,
    fontSize: typography.body.fontSize,
    lineHeight: typography.body.lineHeight,
  },
  card: {
    gap: spacing.lg,
  },
  content: {
    gap: spacing.lg,
  },
  primaryAction: {
    backgroundColor: colors.primaryBlue,
  },
  primaryActionText: {
    color: colors.white,
  },
  secondaryAction: {
    backgroundColor: colors.blueSurface,
  },
  secondaryActionText: {
    color: colors.primaryBlue,
  },
});

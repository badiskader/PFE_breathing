import { StyleSheet, View } from 'react-native';

import { colors } from '@/theme';

type LoadingSkeletonProps = {
  height?: number;
};

export function LoadingSkeleton({ height = 18 }: LoadingSkeletonProps) {
  return <View accessibilityLabel="Loading" style={[styles.skeleton, { height }]} />;
}

const styles = StyleSheet.create({
  skeleton: {
    backgroundColor: colors.mutedSurface,
    borderRadius: 8,
    width: '100%',
  },
});

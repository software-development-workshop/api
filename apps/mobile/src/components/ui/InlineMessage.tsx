import React from 'react';
import { View, StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import { AppText } from './AppText';

export interface InlineMessageProps {
  message: string;
  variant?: 'error' | 'warning' | 'info';
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function InlineMessage({
  message,
  variant = 'error',
  style,
  testID,
}: InlineMessageProps) {
  if (!message) return null;

  const isError = variant === 'error';
  const textColor = isError ? colors.error : colors.text;
  const borderColor = isError ? colors.error : colors.separator;

  return (
    <View
      style={[
        styles.container,
        { borderColor },
        isError ? styles.errorBg : styles.warningBg,
        style,
      ]}
      accessible={true}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      testID={testID ?? 'inline-message'}
    >
      <AppText variant="caption" color={textColor} style={styles.text}>
        {message}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 8,
    borderWidth: 1,
    marginVertical: spacing.sm,
  },
  errorBg: {
    backgroundColor: 'rgba(244, 33, 46, 0.1)',
  },
  warningBg: {
    backgroundColor: colors.surface,
  },
  text: {
    lineHeight: 18,
  },
});

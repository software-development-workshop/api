import React, { useState } from 'react';
import {
  View,
  TextInput,
  TextInputProps,
  StyleSheet,
  ViewStyle,
  StyleProp,
} from 'react-native';
import { colors } from '../../theme/colors';
import { layout, spacing } from '../../theme/spacing';
import { AppText } from './AppText';

export interface TextFieldProps extends TextInputProps {
  label: string;
  error?: string | null;
  containerStyle?: StyleProp<ViewStyle>;
  testID?: string;
}

export function TextField({
  label,
  error,
  containerStyle,
  style,
  onFocus,
  onBlur,
  testID,
  accessibilityLabel,
  ...rest
}: TextFieldProps) {
  const [isFocused, setIsFocused] = useState(false);

  const hasError = Boolean(error);
  const borderColor = hasError
    ? colors.error
    : isFocused
      ? colors.focus
      : colors.inputBorder;

  return (
    <View style={[styles.container, containerStyle]}>
      <AppText
        variant="caption"
        color={hasError ? colors.error : colors.textMuted}
        style={styles.label}
      >
        {label}
      </AppText>
      <TextInput
        style={[
          styles.input,
          { borderColor },
          hasError && styles.inputError,
          style,
        ]}
        placeholderTextColor={colors.textMuted}
        selectionColor={colors.focus}
        accessibilityLabel={accessibilityLabel || label}
        accessibilityHint={error || undefined}
        testID={testID}
        onFocus={(e) => {
          setIsFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setIsFocused(false);
          onBlur?.(e);
        }}
        {...rest}
      />
      {hasError ? (
        <AppText
          variant="caption"
          color={colors.error}
          style={styles.errorText}
          testID={testID ? `${testID}-error` : 'field-error'}
        >
          {error}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    marginBottom: spacing.md,
  },
  label: {
    marginBottom: spacing.xs,
    fontWeight: '700',
  },
  input: {
    minHeight: layout.inputMinHeight,
    borderRadius: layout.inputRadius,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 16,
    lineHeight: 24,
    color: colors.text,
    backgroundColor: colors.background,
  },
  inputError: {
    borderColor: colors.error,
  },
  errorText: {
    marginTop: spacing.xs,
  },
});

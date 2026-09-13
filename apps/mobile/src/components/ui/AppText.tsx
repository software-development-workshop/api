import React from 'react';
import {
  Text as RNText,
  TextProps as RNTextProps,
  StyleSheet,
} from 'react-native';
import { colors } from '../../theme/colors';
import { typography, TypographyVariant } from '../../theme/typography';

export interface AppTextProps extends RNTextProps {
  variant?: TypographyVariant;
  color?: string;
  children?: React.ReactNode;
}

export function AppText({
  variant = 'body',
  color = colors.text,
  style,
  children,
  ...rest
}: AppTextProps) {
  const variantStyle = typography[variant];

  return (
    <RNText style={[styles.base, variantStyle, { color }, style]} {...rest}>
      {children}
    </RNText>
  );
}

const styles = StyleSheet.create({
  base: {
    fontFamily: 'System',
    includeFontPadding: false,
  },
});

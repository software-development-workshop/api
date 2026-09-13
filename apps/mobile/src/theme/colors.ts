export const colors = {
  background: '#000000',
  surface: '#16181C',
  text: '#E7E9EA',
  textMuted: '#8B98A5',
  separator: '#2F3336',
  inputBorder: '#536471',
  actionBackground: '#EFF3F4',
  actionText: '#0F1419',
  focus: '#1D9BF0',
  error: '#F4212E',
} as const;

export type ColorToken = keyof typeof colors;

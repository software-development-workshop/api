import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { AppText } from '../../src/components/ui/AppText';
import { Button } from '../../src/components/ui/Button';
import { TextField } from '../../src/components/ui/TextField';
import { InlineMessage } from '../../src/components/ui/InlineMessage';
import { Header } from '../../src/components/ui/Header';
import { Screen } from '../../src/components/ui/Screen';
import { colors } from '../../src/theme/colors';

describe('UI Components', () => {
  describe('AppText', () => {
    it('renders with default variant and text', async () => {
      const { getByText } = await render(<AppText>Hello World</AppText>);
      const element = getByText('Hello World');
      expect(element).toBeTruthy();
    });

    it('renders with custom variant and color', async () => {
      const { getByText } = await render(
        <AppText variant="loginTitle" color={colors.focus}>
          Custom Text
        </AppText>
      );
      const element = getByText('Custom Text');
      expect(element.props.style).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ fontSize: 32 }),
          expect.objectContaining({ color: colors.focus }),
        ])
      );
    });
  });

  describe('Button', () => {
    it('renders title and responds to press', async () => {
      const onPress = jest.fn();
      const { getByText, getByRole } = await render(
        <Button title="Click Me" onPress={onPress} />
      );

      const button = getByRole('button');
      expect(getByText('Click Me')).toBeTruthy();

      await fireEvent.press(button);
      expect(onPress).toHaveBeenCalledTimes(1);
    });

    it('shows loading indicator and prevents press when loading', async () => {
      const onPress = jest.fn();
      const { getByTestId, queryByText } = await render(
        <Button
          title="Submitting"
          onPress={onPress}
          loading
          testID="test-btn"
        />
      );

      expect(getByTestId('test-btn-loading')).toBeTruthy();
      expect(queryByText('Submitting')).toBeNull();

      await fireEvent.press(getByTestId('test-btn'));
      expect(onPress).not.toHaveBeenCalled();
    });

    it('prevents press when disabled', async () => {
      const onPress = jest.fn();
      const { getByRole } = await render(
        <Button title="Disabled" onPress={onPress} disabled />
      );

      await fireEvent.press(getByRole('button'));
      expect(onPress).not.toHaveBeenCalled();
    });

    it('renders secondary variant', async () => {
      const { getByRole } = await render(
        <Button title="Secondary" variant="secondary" onPress={() => {}} />
      );
      expect(getByRole('button')).toBeTruthy();
    });
  });

  describe('TextField', () => {
    it('renders label, input, and updates value', async () => {
      const onChangeText = jest.fn();
      const { getByText, getByPlaceholderText } = await render(
        <TextField
          label="Email"
          placeholder="user@example.com"
          value=""
          onChangeText={onChangeText}
        />
      );

      expect(getByText('Email')).toBeTruthy();
      const input = getByPlaceholderText('user@example.com');
      await fireEvent.changeText(input, 'test@example.com');
      expect(onChangeText).toHaveBeenCalledWith('test@example.com');
    });

    it('handles focus and blur states', async () => {
      const onFocus = jest.fn();
      const onBlur = jest.fn();
      const { getByTestId } = await render(
        <TextField
          label="User"
          testID="text-input"
          onFocus={onFocus}
          onBlur={onBlur}
        />
      );

      const input = getByTestId('text-input');
      await fireEvent(input, 'focus');
      expect(onFocus).toHaveBeenCalled();

      await fireEvent(input, 'blur');
      expect(onBlur).toHaveBeenCalled();
    });

    it('displays error message and styles', async () => {
      const { getByText, getByTestId } = await render(
        <TextField
          label="Password"
          error="Password too short"
          testID="pwd-input"
        />
      );

      expect(getByText('Password too short')).toBeTruthy();
      expect(getByTestId('pwd-input-error')).toBeTruthy();
    });
  });

  describe('InlineMessage', () => {
    it('renders error message with alert role', async () => {
      const { getByRole, getByText } = await render(
        <InlineMessage message="Invalid password" variant="error" />
      );

      expect(getByRole('alert')).toBeTruthy();
      expect(getByText('Invalid password')).toBeTruthy();
    });

    it('renders warning variant', async () => {
      const { getByText } = await render(
        <InlineMessage message="Signed out on server" variant="warning" />
      );
      expect(getByText('Signed out on server')).toBeTruthy();
    });

    it('returns null if message is empty', async () => {
      const { toJSON } = await render(<InlineMessage message="" />);
      expect(toJSON()).toBeNull();
    });
  });

  describe('Header', () => {
    it('renders title and actions', async () => {
      const { getByText } = await render(
        <Header
          title="App Header"
          leftAction={<AppText>Back</AppText>}
          rightAction={<AppText>Edit</AppText>}
        />
      );

      expect(getByText('App Header')).toBeTruthy();
      expect(getByText('Back')).toBeTruthy();
      expect(getByText('Edit')).toBeTruthy();
    });
  });

  describe('Screen', () => {
    it('renders non-scrollable container', async () => {
      const { getByText, getByTestId } = await render(
        <Screen testID="test-screen">
          <AppText>Inside Screen</AppText>
        </Screen>
      );

      expect(getByTestId('test-screen')).toBeTruthy();
      expect(getByText('Inside Screen')).toBeTruthy();
    });

    it('renders scrollable container when scrollable={true}', async () => {
      const { getByTestId, getByText } = await render(
        <Screen scrollable testID="scroll-screen">
          <AppText>Scroll content</AppText>
        </Screen>
      );

      expect(getByTestId('scroll-screen-scroll')).toBeTruthy();
      expect(getByText('Scroll content')).toBeTruthy();
    });
  });
});

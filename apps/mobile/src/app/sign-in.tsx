import React, { useState, useRef, useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { Screen } from '../components/ui/Screen';
import { AppText } from '../components/ui/AppText';
import { TextField } from '../components/ui/TextField';
import { Button } from '../components/ui/Button';
import { InlineMessage } from '../components/ui/InlineMessage';
import { useSession } from '../auth/SessionContext';
import { colors } from '../theme/colors';
import { spacing, layout } from '../theme/spacing';
import { ApiError } from '../api/http';

export default function SignInScreen() {
  const { signIn, sessionNotice, clearSessionNotice } = useSession();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isSubmittingRef = useRef(false);

  useEffect(() => {
    return () => {
      isSubmittingRef.current = false;
    };
  }, []);

  const handleIdentifierChange = (text: string) => {
    setIdentifier(text);
    if (errorMessage) setErrorMessage(null);
    if (sessionNotice) clearSessionNotice?.();
  };

  const handlePasswordChange = (text: string) => {
    setPassword(text);
    if (errorMessage) setErrorMessage(null);
    if (sessionNotice) clearSessionNotice?.();
  };

  const handleSubmit = async () => {
    if (isSubmittingRef.current || isSubmitting) {
      return;
    }

    const trimmedIdentifier = identifier.trim();
    if (!trimmedIdentifier || !password) {
      setErrorMessage('Por favor, completá todos los campos.');
      return;
    }

    isSubmittingRef.current = true;
    setIsSubmitting(true);
    setErrorMessage(null);
    if (sessionNotice) clearSessionNotice?.();

    try {
      await signIn(trimmedIdentifier, password);
      setPassword('');
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(
          'Ocurrió un error inesperado. Por favor, intentá nuevamente.'
        );
      }
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <Screen
      scrollable
      keyboardAvoiding
      paddingHorizontal={layout.screenPaddingLogin}
      testID="sign-in-screen"
    >
      <View style={styles.container}>
        <View style={styles.brandHeader}>
          <AppText
            variant="heading"
            color={colors.textMuted}
            style={styles.brand}
          >
            UdeSA-X
          </AppText>
          <AppText
            variant="loginTitle"
            color={colors.text}
            style={styles.title}
          >
            Iniciá sesión
          </AppText>
        </View>

        {sessionNotice ? (
          <InlineMessage
            message={sessionNotice}
            variant="warning"
            testID="session-notice-message"
          />
        ) : null}

        {errorMessage ? (
          <InlineMessage
            message={errorMessage}
            variant="error"
            testID="sign-in-error-message"
          />
        ) : null}

        <View style={styles.form}>
          <TextField
            label="Email o usuario"
            value={identifier}
            onChangeText={handleIdentifierChange}
            placeholder="usuario@ejemplo.com o @usuario"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            editable={!isSubmitting}
            testID="identifier-input"
            accessibilityLabel="Email o usuario"
          />

          <TextField
            label="Contraseña"
            value={password}
            onChangeText={handlePasswordChange}
            placeholder="••••••••"
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            editable={!isSubmitting}
            testID="password-input"
            accessibilityLabel="Contraseña"
          />

          <Button
            title="Ingresar"
            onPress={handleSubmit}
            loading={isSubmitting}
            disabled={isSubmitting}
            testID="submit-button"
            accessibilityLabel="Ingresar a la aplicación"
            style={styles.submitButton}
          />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
  },
  brandHeader: {
    marginBottom: spacing.xl,
  },
  brand: {
    marginBottom: spacing.xs,
  },
  title: {
    letterSpacing: -0.5,
  },
  form: {
    marginTop: spacing.md,
  },
  submitButton: {
    marginTop: spacing.md,
  },
});

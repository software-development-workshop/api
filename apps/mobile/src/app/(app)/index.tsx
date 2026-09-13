import React, { useState, useRef, useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { Screen } from '../../components/ui/Screen';
import { Header } from '../../components/ui/Header';
import { AppText } from '../../components/ui/AppText';
import { Button } from '../../components/ui/Button';
import { useSession } from '../../auth/SessionContext';
import { colors } from '../../theme/colors';
import { spacing, layout } from '../../theme/spacing';

export default function HomeScreen() {
  const { signOut } = useSession();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const isSigningOutRef = useRef(false);

  useEffect(() => {
    return () => {
      isSigningOutRef.current = false;
    };
  }, []);

  const handleSignOut = async () => {
    if (isSigningOutRef.current || isSigningOut) {
      return;
    }

    isSigningOutRef.current = true;
    setIsSigningOut(true);

    try {
      await signOut();
    } finally {
      isSigningOutRef.current = false;
      setIsSigningOut(false);
    }
  };

  return (
    <Screen
      scrollable
      paddingHorizontal={layout.screenPaddingApp}
      testID="home-screen"
    >
      <Header title="Inicio" testID="home-header" />
      <View style={styles.container}>
        <View style={styles.content}>
          <AppText
            variant="heading"
            color={colors.text}
            style={styles.statusTitle}
          >
            Sesión iniciada
          </AppText>
          <AppText
            variant="body"
            color={colors.textMuted}
            style={styles.description}
          >
            Bienvenido a UdeSA-X.
          </AppText>
        </View>

        <Button
          title="Cerrar sesión"
          variant="secondary"
          onPress={handleSignOut}
          loading={isSigningOut}
          disabled={isSigningOut}
          testID="sign-out-button"
          accessibilityLabel="Cerrar sesión en esta aplicación"
          style={styles.signOutButton}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'space-between',
    paddingVertical: spacing.xl,
  },
  content: {
    paddingTop: spacing.xl,
  },
  statusTitle: {
    marginBottom: spacing.sm,
  },
  description: {
    lineHeight: 22,
  },
  signOutButton: {
    marginTop: spacing.xl,
  },
});

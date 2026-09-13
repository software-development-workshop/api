import React from 'react';
import { Stack, Redirect } from 'expo-router';
import { useSession } from '../../auth/SessionContext';
import { colors } from '../../theme/colors';

export default function AppLayout() {
  const { session } = useSession();

  if (!session) {
    return <Redirect href="/sign-in" />;
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="index" />
    </Stack>
  );
}

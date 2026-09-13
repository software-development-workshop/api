import {
  renderRouter,
  screen,
  fireEvent,
  waitFor,
  act,
} from 'expo-router/testing-library';
import { router } from 'expo-router';
import RootLayout from '../../src/app/_layout';
import SignInScreen from '../../src/app/sign-in';
import AppLayout from '../../src/app/(app)/_layout';
import HomeScreen from '../../src/app/(app)/index';

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
    },
  });
}

describe('Navigation Layout with expo-router/testing-library', () => {
  const originalEnvAccounts = process.env.EXPO_PUBLIC_ACCOUNTS_API_URL;
  const originalEnvPosts = process.env.EXPO_PUBLIC_POSTS_API_URL;

  beforeEach(() => {
    process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = 'http://localhost:8000';
    process.env.EXPO_PUBLIC_POSTS_API_URL = 'http://localhost:8001';
  });

  afterEach(() => {
    jest.useRealTimers();
    process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = originalEnvAccounts;
    process.env.EXPO_PUBLIC_POSTS_API_URL = originalEnvPosts;
    jest.restoreAllMocks();
  });

  const routes = {
    _layout: RootLayout,
    'sign-in': SignInScreen,
    '(app)/_layout': AppLayout,
    '(app)/index': HomeScreen,
  };

  it('renders sign-in screen initially when unauthenticated', async () => {
    await renderRouter(routes, { initialUrl: '/sign-in' });

    expect(screen.getByTestId('sign-in-screen')).toBeTruthy();
    expect(screen.getByText('Iniciá sesión')).toBeTruthy();
  });

  it('redirects or guards unauthenticated access when opening /(app)', async () => {
    await renderRouter(routes, { initialUrl: '/(app)' });

    // Protected stack guards (app) and renders sign-in
    await waitFor(() => {
      expect(screen.getByTestId('sign-in-screen')).toBeTruthy();
    });
  });

  it('returns to sign-in when the active session expires and refuses the protected route', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValueOnce(
      jsonResponse({
        access_token: 'short-lived-token',
        token_type: 'bearer',
        expires_in: 10,
      })
    );
    await renderRouter(routes, { initialUrl: '/sign-in' });
    await fireEvent.changeText(screen.getByTestId('identifier-input'), 'user');
    await fireEvent.changeText(
      screen.getByTestId('password-input'),
      'synthetic-password'
    );
    await fireEvent.press(screen.getByTestId('submit-button'));
    expect(screen.getByTestId('home-screen')).toBeTruthy();

    await act(() => {
      jest.advanceTimersByTime(10001);
    });
    expect(screen.getByTestId('sign-in-screen')).toBeTruthy();
    await act(() => {
      router.navigate('/');
    });
    expect(screen.getByTestId('sign-in-screen')).toBeTruthy();
    expect(screen.queryByTestId('home-screen')).toBeNull();
    expect(router.canGoBack()).toBe(false);
  });

  it('shows an unconfirmed revocation notice on the remounted login screen', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'logout-notice-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockRejectedValueOnce(new TypeError('Offline'));
    await renderRouter(routes, { initialUrl: '/sign-in' });
    await fireEvent.changeText(screen.getByTestId('identifier-input'), 'user');
    await fireEvent.changeText(
      screen.getByTestId('password-input'),
      'synthetic-password'
    );
    await fireEvent.press(screen.getByTestId('submit-button'));
    await fireEvent.press(screen.getByTestId('sign-out-button'));
    expect(screen.getByTestId('sign-in-screen')).toBeTruthy();
    expect(
      screen.getByText(
        'Saliste de este dispositivo. No pudimos confirmar el cierre de sesión en el servidor'
      )
    ).toBeTruthy();
    expect(screen.queryByTestId('home-screen')).toBeNull();
    expect(router.canGoBack()).toBe(false);
  });

  it('authenticates user and navigates from sign-in to home screen, then signs out', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'valid-test-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await renderRouter(routes, { initialUrl: '/sign-in' });

    expect(screen.getByTestId('sign-in-screen')).toBeTruthy();

    await fireEvent.changeText(
      screen.getByTestId('identifier-input'),
      'verified.user@example.com'
    );
    await fireEvent.changeText(
      screen.getByTestId('password-input'),
      'SecurePass123!'
    );
    await fireEvent.press(screen.getByTestId('submit-button'));

    // Successfully transitioned to protected home screen
    await waitFor(() => {
      expect(screen.getByTestId('home-screen')).toBeTruthy();
      expect(screen.getByText('Sesión iniciada')).toBeTruthy();
    });
    expect(router.canGoBack()).toBe(false);

    // Now sign out from home screen
    await fireEvent.press(screen.getByTestId('sign-out-button'));

    // Transitioned back to sign-in screen
    await waitFor(() => {
      expect(screen.getByTestId('sign-in-screen')).toBeTruthy();
    });
    expect(router.canGoBack()).toBe(false);
  });
});

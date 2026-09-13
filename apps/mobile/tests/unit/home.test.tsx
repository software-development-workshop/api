import React from 'react';
import { render, userEvent, waitFor, act } from '@testing-library/react-native';
import HomeScreen from '../../src/app/(app)/index';
import { SessionProvider, useSession } from '../../src/auth/SessionContext';

function jsonResponse(
  data: unknown,
  status = 200,
  headers: Record<string, string> = {}
): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...headers,
    },
  });
}

describe('HomeScreen', () => {
  const originalEnvAccounts = process.env.EXPO_PUBLIC_ACCOUNTS_API_URL;
  const originalEnvPosts = process.env.EXPO_PUBLIC_POSTS_API_URL;

  beforeEach(() => {
    process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = 'http://localhost:8000';
    process.env.EXPO_PUBLIC_POSTS_API_URL = 'http://localhost:8001';
  });

  afterEach(() => {
    process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = originalEnvAccounts;
    process.env.EXPO_PUBLIC_POSTS_API_URL = originalEnvPosts;
    jest.restoreAllMocks();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <SessionProvider>{children}</SessionProvider>
  );

  it('renders header, session status, and logout button', async () => {
    const { getByText, getByTestId } = await render(<HomeScreen />, {
      wrapper,
    });

    expect(getByText('Inicio')).toBeTruthy();
    expect(getByText('Sesión iniciada')).toBeTruthy();
    expect(getByTestId('sign-out-button')).toBeTruthy();
  });

  it('calls signOut and shows loading state when clicking logout', async () => {
    let resolveLogout!: (value: Response) => void;
    const logoutPromise = new Promise<Response>((resolve) => {
      resolveLogout = resolve;
    });

    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'token-123',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockReturnValueOnce(logoutPromise);

    const SetupContainer = () => {
      const { signIn } = useSession();
      React.useEffect(() => {
        signIn('test', 'pw');
      }, [signIn]);
      return <HomeScreen />;
    };

    const { getByTestId, queryByTestId } = await render(<SetupContainer />, {
      wrapper,
    });

    await waitFor(() => {
      expect(getByTestId('sign-out-button')).toBeTruthy();
    });

    await userEvent.press(getByTestId('sign-out-button'));

    expect(getByTestId('sign-out-button-loading')).toBeTruthy();

    await act(async () => {
      resolveLogout(new Response(null, { status: 204 }));
    });

    await waitFor(() => {
      expect(queryByTestId('sign-out-button-loading')).toBeNull();
    });
  });

  it('prevents double tap when clicking logout', async () => {
    let resolveLogout!: (value: Response) => void;
    const logoutPromise = new Promise<Response>((resolve) => {
      resolveLogout = resolve;
    });

    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'token-123',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockReturnValue(logoutPromise);

    const SetupContainer = () => {
      const { signIn } = useSession();
      React.useEffect(() => {
        signIn('test', 'pw');
      }, [signIn]);
      return <HomeScreen />;
    };

    const { getByTestId } = await render(<SetupContainer />, { wrapper });

    await waitFor(() => {
      expect(getByTestId('sign-out-button')).toBeTruthy();
    });

    const logoutBtn = getByTestId('sign-out-button');
    await userEvent.press(logoutBtn);
    await userEvent.press(logoutBtn);

    // Initial sign in (1) + only 1 logout call (2)
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveLogout(new Response(null, { status: 204 }));
    });
  });
});

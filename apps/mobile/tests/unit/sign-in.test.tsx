import React from 'react';
import {
  render,
  fireEvent,
  userEvent,
  waitFor,
  act,
} from '@testing-library/react-native';
import SignInScreen from '../../src/app/sign-in';
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

describe('SignInScreen', () => {
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

  it('renders brand, title, inputs, and submit button', async () => {
    const { getByText, getByTestId } = await render(<SignInScreen />, {
      wrapper,
    });

    expect(getByText('UdeSA-X')).toBeTruthy();
    expect(getByText('Iniciá sesión')).toBeTruthy();
    expect(getByTestId('identifier-input')).toBeTruthy();
    expect(getByTestId('password-input')).toBeTruthy();
    expect(getByTestId('submit-button')).toBeTruthy();
  });

  it('shows error if submitted with empty fields', async () => {
    const { getByTestId, getByText } = await render(<SignInScreen />, {
      wrapper,
    });

    await fireEvent.press(getByTestId('submit-button'));

    await waitFor(() => {
      expect(getByText('Por favor, completá todos los campos.')).toBeTruthy();
    });
  });

  it('submits credentials, displays loading, and clears password on success', async () => {
    let resolveLogin!: (value: Response) => void;
    const loginPromise = new Promise<Response>((resolve) => {
      resolveLogin = resolve;
    });
    jest.spyOn(global, 'fetch').mockReturnValue(loginPromise);

    const { getByTestId, queryByTestId } = await render(<SignInScreen />, {
      wrapper,
    });

    await fireEvent.changeText(
      getByTestId('identifier-input'),
      'user@example.com'
    );
    await fireEvent.changeText(getByTestId('password-input'), 'secret123');

    await userEvent.press(getByTestId('submit-button'));

    expect(getByTestId('submit-button-loading')).toBeTruthy();

    await act(async () => {
      resolveLogin(
        jsonResponse({
          access_token: 'auth-success-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      );
    });

    await waitFor(() => {
      expect(queryByTestId('submit-button-loading')).toBeNull();
      expect(getByTestId('password-input').props.value).toBe('');
    });
  });

  it('prevents duplicate submission on immediate double tap', async () => {
    let resolveLogin!: (value: Response) => void;
    const loginPromise = new Promise<Response>((resolve) => {
      resolveLogin = resolve;
    });
    const fetchSpy = jest.spyOn(global, 'fetch').mockReturnValue(loginPromise);

    const { getByTestId } = await render(<SignInScreen />, { wrapper });

    await fireEvent.changeText(
      getByTestId('identifier-input'),
      'user@example.com'
    );
    await fireEvent.changeText(getByTestId('password-input'), 'secret123');

    const button = getByTestId('submit-button');

    await userEvent.press(button);
    await userEvent.press(button);

    expect(fetchSpy).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveLogin(
        jsonResponse({
          access_token: 'double-tap-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      );
    });
  });

  it('displays ApiError message when login fails and allows retry', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(
        {
          type: 'https://udesa-x.dev/problems/invalid-credentials',
          status: 401,
          title: 'Invalid credentials',
          detail: 'Invalid credentials.',
        },
        401,
        { 'content-type': 'application/problem+json' }
      )
    );

    const { getByTestId, getByText, queryByText } = await render(
      <SignInScreen />,
      { wrapper }
    );

    await fireEvent.changeText(
      getByTestId('identifier-input'),
      'bad@example.com'
    );
    await fireEvent.changeText(getByTestId('password-input'), 'wrongpw');

    await fireEvent.press(getByTestId('submit-button'));

    await waitFor(() => {
      expect(
        getByText('Email, usuario o contraseña incorrectos.')
      ).toBeTruthy();
    });

    await fireEvent.changeText(
      getByTestId('identifier-input'),
      'new@example.com'
    );
    expect(queryByText('Email, usuario o contraseña incorrectos.')).toBeNull();
  });

  it('shows a safe network error without exposing internal details', async () => {
    jest.spyOn(global, 'fetch').mockImplementation(() => {
      throw new Error('Unexpected catastrophic error');
    });

    const { getByTestId, getByText, queryByText } = await render(
      <SignInScreen />,
      { wrapper }
    );

    await fireEvent.changeText(
      getByTestId('identifier-input'),
      'user@example.com'
    );
    await fireEvent.changeText(getByTestId('password-input'), 'secret123');
    await fireEvent.press(getByTestId('submit-button'));

    await waitFor(() => {
      expect(getByText(/No pudimos conectar/)).toBeTruthy();
      expect(queryByText(/catastrophic/)).toBeNull();
    });
  });

  it('displays sessionNotice and clears it on text change', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'token-abc',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockRejectedValueOnce(new TypeError('Network offline'));
    const TestNoticeContainer = () => {
      const { signIn, signOut } = useSession();
      React.useEffect(() => {
        void signIn('user', 'pass').then(() => signOut());
      }, [signIn, signOut]);

      return <SignInScreen />;
    };

    const { getByText, queryByText, getByTestId } = await render(
      <TestNoticeContainer />,
      {
        wrapper,
      }
    );

    await waitFor(() => {
      expect(
        getByText(
          'Saliste de este dispositivo. No pudimos confirmar el cierre de sesión en el servidor'
        )
      ).toBeTruthy();
    });

    await fireEvent.changeText(getByTestId('identifier-input'), 'new-user');

    await waitFor(() => {
      expect(
        queryByText(
          'Saliste de este dispositivo. No pudimos confirmar el cierre de sesión en el servidor'
        )
      ).toBeNull();
    });
  });
});

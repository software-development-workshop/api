import React from 'react';
import { renderHook, act } from '@testing-library/react-native';
import { AppState, AppStateStatus } from 'react-native';
import {
  SessionProvider,
  useSession,
  validateSessionResponse,
} from '../../src/auth/SessionContext';
import { RawSessionResponse } from '../../src/auth/types';

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

describe('validateSessionResponse', () => {
  it('accepts valid session response and returns token and expiresIn', () => {
    const raw: RawSessionResponse = {
      access_token: 'valid-jwt-token',
      token_type: 'bearer',
      expires_in: 3600,
    };
    const result = validateSessionResponse(raw);
    expect(result).toEqual({
      accessToken: 'valid-jwt-token',
      expiresIn: 3600,
    });
  });

  it('accepts uppercase BEARER token type', () => {
    const raw: RawSessionResponse = {
      access_token: 'valid-jwt-token',
      token_type: 'BEARER',
      expires_in: 3600,
    };
    const result = validateSessionResponse(raw);
    expect(result.accessToken).toBe('valid-jwt-token');
  });

  it('rejects missing or empty access_token', () => {
    expect(() =>
      validateSessionResponse({
        access_token: '',
        token_type: 'bearer',
        expires_in: 3600,
      })
    ).toThrow('token de acceso inválido');

    expect(() =>
      validateSessionResponse({
        access_token: null,
        token_type: 'bearer',
        expires_in: 3600,
      })
    ).toThrow('token de acceso inválido');
  });

  it('rejects non-bearer token_type', () => {
    expect(() =>
      validateSessionResponse({
        access_token: 'tok',
        token_type: 'basic',
        expires_in: 3600,
      })
    ).toThrow('tipo de token no soportado');
  });

  it('rejects non-finite, zero or negative expires_in', () => {
    expect(() =>
      validateSessionResponse({
        access_token: 'tok',
        token_type: 'bearer',
        expires_in: 0,
      })
    ).toThrow('tiempo de expiración inválido');

    expect(() =>
      validateSessionResponse({
        access_token: 'tok',
        token_type: 'bearer',
        expires_in: -10,
      })
    ).toThrow('tiempo de expiración inválido');

    expect(() =>
      validateSessionResponse({
        access_token: 'tok',
        token_type: 'bearer',
        expires_in: Infinity,
      })
    ).toThrow('tiempo de expiración inválido');
  });
});

describe('SessionProvider and useSession', () => {
  const originalEnvAccounts = process.env.EXPO_PUBLIC_ACCOUNTS_API_URL;
  const originalEnvPosts = process.env.EXPO_PUBLIC_POSTS_API_URL;

  beforeEach(() => {
    jest
      .spyOn(AppState, 'addEventListener')
      .mockImplementation(() => ({ remove: jest.fn() }));
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

  it('throws an error if useSession is used outside SessionProvider', async () => {
    const consoleSpy = jest
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    await expect(renderHook(() => useSession())).rejects.toThrow(
      'useSession must be used within a SessionProvider'
    );
    consoleSpy.mockRestore();
  });

  it('starts with session as null and successfully signs in and exposes getSession()', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse({
        access_token: 'jwt-abc-123',
        token_type: 'bearer',
        expires_in: 3600,
      })
    );

    const { result } = await renderHook(() => useSession(), { wrapper });

    expect(result.current.session).toBeNull();
    expect(result.current.getSession()).toBeNull();
    expect(result.current.sessionNotice).toBeNull();

    await act(async () => {
      await result.current.signIn('alice@example.com', 'password123');
    });

    expect(result.current.session).not.toBeNull();
    expect(result.current.session?.accessToken).toBe('jwt-abc-123');
    expect(result.current.getSession()?.accessToken).toBe('jwt-abc-123');
    expect(result.current.session?.expiresAt).toBeGreaterThan(Date.now());
  });

  it('deduplicates simultaneous signIn calls', async () => {
    let resolveFetch!: (value: Response) => void;
    const pendingPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });

    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockReturnValue(pendingPromise);

    const { result } = await renderHook(() => useSession(), { wrapper });

    let p1!: Promise<void>;
    let p2!: Promise<void>;

    await act(() => {
      p1 = result.current.signIn('alice', 'pw');
      p2 = result.current.signIn('alice', 'pw');
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFetch(
        jsonResponse({
          access_token: 'tok-dedup',
          token_type: 'bearer',
          expires_in: 1800,
        })
      );
      await Promise.all([p1, p2]);
    });

    expect(result.current.session?.accessToken).toBe('tok-dedup');
    expect(result.current.getSession()?.accessToken).toBe('tok-dedup');
  });

  it('discards stale signIn response if invalidated during network wait', async () => {
    let resolveFetch!: (value: Response) => void;
    const pendingPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });

    jest.spyOn(global, 'fetch').mockReturnValue(pendingPromise);

    const { result } = await renderHook(() => useSession(), { wrapper });

    let p1!: Promise<void>;
    await act(() => {
      p1 = result.current.signIn('slow-user', 'pw');
    });

    await act(() => {
      result.current.invalidate();
    });

    await act(async () => {
      resolveFetch(
        jsonResponse({
          access_token: 'stale-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      );
      await p1;
    });

    expect(result.current.session).toBeNull();
    expect(result.current.getSession()).toBeNull();
  });

  it('automatically invalidates session when active expiry timer fires', async () => {
    jest.useFakeTimers();
    try {
      jest.spyOn(global, 'fetch').mockResolvedValue(
        jsonResponse({
          access_token: 'expiring-token',
          token_type: 'bearer',
          expires_in: 10,
        })
      );

      const { result } = await renderHook(() => useSession(), { wrapper });

      await act(async () => {
        await result.current.signIn('user', 'pw');
      });

      expect(result.current.session).not.toBeNull();

      await act(() => {
        jest.advanceTimersByTime(10001);
      });

      expect(result.current.session).toBeNull();
      expect(result.current.getSession()).toBeNull();
    } finally {
      jest.useRealTimers();
    }
  });

  it('invalidates immediately if remaining time is already non-positive', async () => {
    const { result } = await renderHook(() => useSession(), { wrapper });

    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse({
        access_token: 'past-token',
        token_type: 'bearer',
        expires_in: 1,
      })
    );

    const realNow = Date.now;
    let mockedTime = 1000000;
    Date.now = jest.fn(() => mockedTime);

    try {
      await act(async () => {
        await result.current.signIn('user', 'pw');
        // Simulate a delayed commit: the effect first runs after the token expired.
        mockedTime += 2000;
      });

      expect(result.current.session).toBeNull();
    } finally {
      Date.now = realNow;
    }
  });

  it('invalidates expired session when app returns to foreground (active)', async () => {
    let appStateListener: ((state: AppStateStatus) => void) | undefined;
    const addEventListenerSpy = jest
      .spyOn(AppState, 'addEventListener')
      .mockImplementation((event: string, listener: unknown) => {
        if (event === 'change') {
          appStateListener = listener as (state: AppStateStatus) => void;
        }
        return { remove: jest.fn() } as unknown as ReturnType<
          typeof AppState.addEventListener
        >;
      });

    const realNow = Date.now;
    let currentTime = 10000;
    Date.now = jest.fn(() => currentTime);

    try {
      jest.spyOn(global, 'fetch').mockResolvedValue(
        jsonResponse({
          access_token: 'foreground-test-token',
          token_type: 'bearer',
          expires_in: 60,
        })
      );

      const { result } = await renderHook(() => useSession(), { wrapper });

      await act(async () => {
        await result.current.signIn('user', 'pw');
      });

      expect(result.current.session).not.toBeNull();

      currentTime += 65000;

      await act(() => {
        appStateListener?.('active');
      });

      expect(result.current.session).toBeNull();
    } finally {
      addEventListenerSpy.mockRestore();
      Date.now = realNow;
    }
  });

  it('signOut clears local session immediately, calls logout endpoint, and returns revoked: true on success', async () => {
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'logout-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const { result } = await renderHook(() => useSession(), { wrapper });

    await act(async () => {
      await result.current.signIn('user', 'pw');
    });

    expect(result.current.session).not.toBeNull();

    let signOutResult: { revoked: boolean } | undefined;
    await act(async () => {
      signOutResult = await result.current.signOut();
    });

    expect(signOutResult).toEqual({ revoked: true });
    expect(result.current.session).toBeNull();
    expect(result.current.getSession()).toBeNull();
    expect(result.current.sessionNotice).toBeNull();
    expect(fetchSpy).toHaveBeenLastCalledWith(
      'http://localhost:8000/api/v1/sessions/logout',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer logout-token',
        }),
      })
    );
  });

  it('signOut does not claim server revocation when there is no active session', async () => {
    const { result } = await renderHook(() => useSession(), { wrapper });
    let res!: { revoked: boolean };
    await act(async () => {
      res = await result.current.signOut();
    });
    expect(res).toEqual({ revoked: false });
  });

  it('signOut clears local session and sets warning notice when server revocation fails', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'logout-fail-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockRejectedValueOnce(new TypeError('Network offline'));

    const { result } = await renderHook(() => useSession(), { wrapper });

    await act(async () => {
      await result.current.signIn('user', 'pw');
    });

    expect(result.current.session).not.toBeNull();

    let signOutResult: { revoked: boolean } | undefined;
    await act(async () => {
      signOutResult = await result.current.signOut();
    });

    expect(signOutResult).toEqual({ revoked: false });
    expect(result.current.session).toBeNull();
    expect(result.current.sessionNotice).toBe(
      'Saliste de este dispositivo. No pudimos confirmar el cierre de sesión en el servidor'
    );

    await act(() => {
      result.current.clearSessionNotice?.();
    });
    expect(result.current.sessionNotice).toBeNull();
  });

  it('deduplicates concurrent signOut calls', async () => {
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'logout-concurrent',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockResolvedValue(new Response(null, { status: 204 }));

    const { result } = await renderHook(() => useSession(), { wrapper });

    await act(async () => {
      await result.current.signIn('user', 'pw');
    });

    let p1!: Promise<{ revoked: boolean }>;
    let p2!: Promise<{ revoked: boolean }>;

    await act(async () => {
      p1 = result.current.signOut();
      p2 = result.current.signOut();
      const [r1, r2] = await Promise.all([p1, p2]);
      expect(r1).toEqual({ revoked: true });
      expect(r2).toEqual({ revoked: true });
    });

    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});

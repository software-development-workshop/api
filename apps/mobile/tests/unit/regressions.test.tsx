import React from 'react';
import { act, renderHook } from '@testing-library/react-native';
import { SessionProvider, useSession } from '../../src/auth/SessionContext';
import { useAuthenticatedApi } from '../../src/api/useAuthenticatedApi';
import { requestJson } from '../../src/api/http';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

const loginResponse = (token: string) =>
  jsonResponse({
    access_token: token,
    token_type: 'bearer',
    expires_in: 1800,
  });
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SessionProvider>{children}</SessionProvider>
);

beforeEach(() => {
  process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = 'http://localhost:8000';
  process.env.EXPO_PUBLIC_POSTS_API_URL = 'http://localhost:8001';
});

afterEach(() => {
  jest.restoreAllMocks();
});

it('signing out cancels an in-flight login even before a token arrives', async () => {
  const pendingLogin = deferred<Response>();
  jest.spyOn(global, 'fetch').mockReturnValue(pendingLogin.promise);
  const { result } = await renderHook(() => useSession(), { wrapper });
  let login!: Promise<void>;
  await act(() => {
    login = result.current.signIn('alice', 'test-only');
  });
  await act(async () => {
    await result.current.signOut();
  });
  await act(async () => {
    pendingLogin.resolve(loginResponse('late-token'));
    await login;
  });
  expect(result.current.session).toBeNull();
});

it('a repeated logout shares the pending revocation result instead of claiming success', async () => {
  const pendingLogout = deferred<Response>();
  const fetchMock = jest
    .spyOn(global, 'fetch')
    .mockResolvedValueOnce(loginResponse('alice-token'))
    .mockReturnValueOnce(pendingLogout.promise);
  const { result } = await renderHook(() => useSession(), { wrapper });
  await act(async () => {
    await result.current.signIn('alice', 'test-only');
  });
  let first!: Promise<{ revoked: boolean }>;
  let second!: Promise<{ revoked: boolean }>;
  await act(() => {
    first = result.current.signOut();
    second = result.current.signOut();
  });
  let results: { revoked: boolean }[] = [];
  await act(async () => {
    pendingLogout.resolve(jsonResponse({ type: 'unavailable' }, 503));
    results = await Promise.all([first, second]);
  });
  expect(results).toEqual([{ revoked: false }, { revoked: false }]);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(result.current.sessionNotice).toContain('No pudimos confirmar');
});

it.each([200, 401])(
  'an old request returning %i cannot alter a newer session',
  async (status) => {
    const pendingRequest = deferred<Response>();
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(loginResponse('alice-token'))
      .mockReturnValueOnce(pendingRequest.promise)
      .mockResolvedValueOnce(loginResponse('bob-token'));
    const { result } = await renderHook(
      () => ({ auth: useSession(), api: useAuthenticatedApi() }),
      { wrapper }
    );
    await act(async () => {
      await result.current.auth.signIn('alice', 'test-only');
    });
    const request = result.current.api.request('posts', '/api/v1/posts', {
      method: 'GET',
    });
    const rejection = expect(request).rejects.toMatchObject({ status: 401 });
    await act(() => {
      result.current.auth.invalidate();
    });
    await act(async () => {
      await result.current.auth.signIn('bob', 'test-only');
    });
    await act(async () => {
      pendingRequest.resolve(
        jsonResponse(
          status === 200
            ? { content: 'private to Alice' }
            : { type: 'invalid-access-token' },
          status
        )
      );
      await rejection;
    });
    expect(result.current.auth.session?.accessToken).toBe('bob-token');
  }
);

it('a newer session can sign out while the previous revocation is still pending', async () => {
  const oldLogout = deferred<Response>();
  const fetchMock = jest
    .spyOn(global, 'fetch')
    .mockResolvedValueOnce(loginResponse('alice-token'))
    .mockReturnValueOnce(oldLogout.promise)
    .mockResolvedValueOnce(loginResponse('bob-token'))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  const { result } = await renderHook(() => useSession(), { wrapper });
  await act(async () => {
    await result.current.signIn('alice', 'test-only');
  });
  let oldResult!: Promise<{ revoked: boolean }>;
  await act(() => {
    oldResult = result.current.signOut();
  });
  await act(async () => {
    await result.current.signIn('bob', 'test-only');
  });
  await act(async () => {
    expect(await result.current.signOut()).toEqual({ revoked: true });
  });
  await act(async () => {
    oldLogout.resolve(jsonResponse({}, 503));
    await oldResult;
  });
  expect(result.current.session).toBeNull();
  expect(result.current.sessionNotice).toBeNull();
  expect(fetchMock.mock.calls[3][1]?.headers).toMatchObject({
    Authorization: 'Bearer bob-token',
  });
});

it('does not accept an empty successful non-JSON response as application data', async () => {
  jest
    .spyOn(global, 'fetch')
    .mockResolvedValue(new Response('', { status: 200 }));
  await expect(
    requestJson('accounts', '/api/v1/sessions', { method: 'POST' })
  ).rejects.toMatchObject({ code: 'malformed-response' });
});

it('clears a rejected session even when the HTTP 401 response body cannot be read', async () => {
  const rejected = jsonResponse({ type: 'invalid-access-token' }, 401);
  jest
    .spyOn(rejected, 'text')
    .mockRejectedValue(new TypeError('Connection closed mid-body'));
  jest
    .spyOn(global, 'fetch')
    .mockResolvedValueOnce(loginResponse('rejected-token'))
    .mockResolvedValueOnce(rejected);
  const { result } = await renderHook(
    () => ({ auth: useSession(), api: useAuthenticatedApi() }),
    { wrapper }
  );
  await act(async () => {
    await result.current.auth.signIn('alice', 'test-only');
  });
  await act(async () => {
    await expect(
      result.current.api.request('posts', '/api/v1/posts', { method: 'GET' })
    ).rejects.toMatchObject({ status: 401 });
  });
  expect(result.current.auth.session).toBeNull();
});

it('keeps an unconfirmed revocation warning when a subsequent login attempt fails', async () => {
  const pendingLogout = deferred<Response>();
  jest
    .spyOn(global, 'fetch')
    .mockResolvedValueOnce(loginResponse('alice-token'))
    .mockReturnValueOnce(pendingLogout.promise)
    .mockResolvedValueOnce(jsonResponse({ type: 'invalid-credentials' }, 401));
  const { result } = await renderHook(() => useSession(), { wrapper });
  await act(async () => {
    await result.current.signIn('alice', 'test-only');
  });
  let logout!: Promise<{ revoked: boolean }>;
  await act(() => {
    logout = result.current.signOut();
  });
  await act(async () => {
    await expect(result.current.signIn('alice', 'wrong')).rejects.toMatchObject(
      { status: 401 }
    );
  });
  await act(async () => {
    pendingLogout.resolve(jsonResponse({}, 503));
    await logout;
  });
  expect(result.current.session).toBeNull();
  expect(result.current.sessionNotice).toContain('No pudimos confirmar');
});

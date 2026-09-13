import React from 'react';
import { renderHook, act } from '@testing-library/react-native';
import {
  requestJson,
  ApiError,
  extractErrorCode,
  mapErrorMessage,
  getBaseUrl,
} from '../../src/api/http';
import { useAuthenticatedApi } from '../../src/api/useAuthenticatedApi';
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

function textResponse(
  text: string,
  status = 200,
  headers: Record<string, string> = {}
): Response {
  return new Response(text, {
    status,
    headers,
  });
}

describe('HTTP API client (requestJson)', () => {
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

  it('correctly constructs base URLs with no trailing slashes', () => {
    expect(getBaseUrl('accounts')).toBe('http://localhost:8000');
    expect(getBaseUrl('posts')).toBe('http://localhost:8001');

    process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = 'https://api.example.com/acc///';
    expect(getBaseUrl('accounts')).toBe('https://api.example.com/acc');
  });

  it('throws ApiError when configuration is missing or invalid', () => {
    delete process.env.EXPO_PUBLIC_ACCOUNTS_API_URL;
    expect(() => getBaseUrl('accounts')).toThrow(ApiError);
    expect(() => getBaseUrl('accounts')).toThrow(/faltante/);

    process.env.EXPO_PUBLIC_POSTS_API_URL = 'invalid-url';
    expect(() => getBaseUrl('posts')).toThrow(ApiError);
    expect(() => getBaseUrl('posts')).toThrow(/inválida/);

    process.env.EXPO_PUBLIC_POSTS_API_URL = 'ftp://posts.example.com';
    expect(() => getBaseUrl('posts')).toThrow(ApiError);
  });

  it('extracts error codes from problem types or slugs', () => {
    expect(
      extractErrorCode('https://udesa-x.dev/problems/invalid-credentials')
    ).toBe('invalid-credentials');
    expect(extractErrorCode('unverified-account')).toBe('unverified-account');
    expect(extractErrorCode('')).toBe('http-error');
    expect(extractErrorCode(null)).toBe('http-error');
    expect(extractErrorCode('   ')).toBe('http-error');
  });

  it('maps error codes to friendly Spanish messages', () => {
    expect(mapErrorMessage('invalid-credentials')).toBe(
      'Email, usuario o contraseña incorrectos.'
    );
    expect(mapErrorMessage('unverified-account')).toBe(
      'Tu cuenta aún no fue verificada. Revisá tu casilla de correo.'
    );
    expect(mapErrorMessage('suspended-account')).toBe(
      'Esta cuenta ha sido suspendida.'
    );
    expect(mapErrorMessage('account-temporarily-locked')).toBe(
      'Cuenta bloqueada temporalmente por demasiados intentos fallidos. Intentá más tarde.'
    );
    expect(mapErrorMessage('invalid-access-token')).toBe(
      'Tu sesión no es válida o ha expirado.'
    );
    expect(mapErrorMessage('validation-error')).toBe(
      'Los datos ingresados no son válidos.'
    );
    expect(mapErrorMessage('unknown-slug', 401)).toBe(
      'Tu sesión no es válida o ha expirado.'
    );
    expect(mapErrorMessage('unknown-slug', 403)).toBe(
      'Esta cuenta ha sido suspendida.'
    );
    expect(mapErrorMessage('unknown-slug', 500)).toBe(
      'Ocurrió un error inesperado. Por favor, intentá nuevamente.'
    );
  });

  it('sends JSON requests with proper headers and parses JSON response', async () => {
    const mockResponse = {
      access_token: 'tok-123',
      token_type: 'bearer',
      expires_in: 3600,
    };
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(mockResponse));

    const result = await requestJson('accounts', '/api/v1/sessions', {
      method: 'POST',
      body: { identifier: 'user@example.com', password: 'secretpassword' },
      token: 'bearer-test-token',
    });

    expect(result).toEqual(mockResponse);
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sessions',
      expect.objectContaining({
        method: 'POST',
        headers: {
          Accept: 'application/json, application/problem+json',
          Authorization: 'Bearer bearer-test-token',
          'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify({
          identifier: 'user@example.com',
          password: 'secretpassword',
        }),
      })
    );
  });

  it('normalizes path without leading slash', async () => {
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse({ ok: true }));

    await requestJson('accounts', 'api/v1/test', { method: 'GET' });
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/test',
      expect.anything()
    );
  });

  it('handles 204 No Content without attempting to parse JSON', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(new Response(null, { status: 204 }));

    const result = await requestJson('accounts', '/api/v1/sessions/logout', {
      method: 'POST',
      token: 'some-token',
    });

    expect(result).toBeUndefined();
  });

  it('throws ApiError with problem details code and message on HTTP error', async () => {
    const problemBody = {
      type: 'https://udesa-x.dev/problems/invalid-credentials',
      title: 'Invalid credentials',
      status: 401,
      detail: 'Invalid credentials.',
    };

    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(problemBody, 401, {
        'content-type': 'application/problem+json',
      })
    );

    await expect(
      requestJson('accounts', '/api/v1/sessions', {
        method: 'POST',
        body: { identifier: 'bad', password: 'wrong' },
      })
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
      code: 'invalid-credentials',
      message: 'Email, usuario o contraseña incorrectos.',
    });
  });

  it('falls back to invalid-credentials when 401 has no problem code', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(
        textResponse('Unauthorized', 401, { 'content-type': 'text/plain' })
      );

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'POST', body: {} })
    ).rejects.toMatchObject({
      status: 401,
      code: 'invalid-credentials',
      message: 'Email, usuario o contraseña incorrectos.',
    });
  });

  it('throws malformed-response on invalid JSON when content-type is json', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(
        textResponse('{not-json', 200, { 'content-type': 'application/json' })
      );

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'GET' })
    ).rejects.toMatchObject({
      status: 200,
      code: 'malformed-response',
      message: 'Respuesta inválida del servidor.',
    });
  });

  it('throws malformed-response on unexpected non-JSON body in 200 response', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      textResponse('<html>Server Error</html>', 200, {
        'content-type': 'text/html',
      })
    );

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'GET' })
    ).rejects.toMatchObject({
      status: 200,
      code: 'malformed-response',
    });
  });

  it('converts network failures into network-error ApiError', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'GET' })
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
      code: 'network-error',
      message:
        'No pudimos conectar con el servidor. Comprobá tu conexión a internet e intentá nuevamente.',
    });
  });

  it('converts timeout abort into timeout-error ApiError', async () => {
    const abortError = new Error('The operation was aborted.');
    abortError.name = 'AbortError';
    jest.spyOn(global, 'fetch').mockRejectedValue(abortError);

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'GET' })
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
      code: 'timeout-error',
      message:
        'La solicitud tardó demasiado tiempo. Comprobá tu conexión e intentá nuevamente.',
    });
  });

  it('converts response.text() abort into timeout-error ApiError', async () => {
    const abortError = new Error('Read aborted');
    abortError.name = 'AbortError';
    const fakeResponse = {
      status: 200,
      ok: true,
      headers: { get: () => 'application/json' },
      text: jest.fn().mockRejectedValue(abortError),
    } as unknown as Response;

    jest.spyOn(global, 'fetch').mockResolvedValue(fakeResponse);

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'GET' })
    ).rejects.toMatchObject({
      status: 0,
      code: 'timeout-error',
    });
  });

  it('converts response.text() generic error into network-error ApiError', async () => {
    const fakeResponse = {
      status: 200,
      ok: true,
      headers: { get: () => 'application/json' },
      text: jest.fn().mockRejectedValue(new Error('Connection broken')),
    } as unknown as Response;

    jest.spyOn(global, 'fetch').mockResolvedValue(fakeResponse);

    await expect(
      requestJson('accounts', '/api/v1/sessions', { method: 'GET' })
    ).rejects.toMatchObject({
      status: 0,
      code: 'network-error',
    });
  });
});

describe('useAuthenticatedApi hook', () => {
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

  it('throws 401 and invalidates session when session is null', async () => {
    const { result } = await renderHook(() => useAuthenticatedApi(), {
      wrapper,
    });

    await act(async () => {
      await expect(
        result.current.request('posts', '/api/v1/posts', {
          method: 'POST',
          body: { content: 'test' },
        })
      ).rejects.toMatchObject({
        status: 401,
        code: 'invalid-access-token',
      });
    });
  });

  it('throws 401 and invalidates session when session has expired', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse({
        access_token: 'active-token',
        token_type: 'bearer',
        expires_in: 1,
      })
    );

    const { result } = await renderHook(
      () => ({
        api: useAuthenticatedApi(),
        session: useSession(),
      }),
      { wrapper }
    );

    await act(async () => {
      await result.current.session.signIn('user', 'pass');
    });

    expect(result.current.session.session).not.toBeNull();

    const realNow = Date.now;
    Date.now = jest.fn(() => realNow() + 5000);

    try {
      await act(async () => {
        await expect(
          result.current.api.request('posts', '/api/v1/posts', {
            method: 'GET',
          })
        ).rejects.toMatchObject({
          status: 401,
          code: 'invalid-access-token',
        });
      });

      expect(result.current.session.session).toBeNull();
    } finally {
      Date.now = realNow;
    }
  });

  it('calls requestJson with bearer token and returns result', async () => {
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'my-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockResolvedValueOnce(jsonResponse({ id: 'p1', content: 'hello' }, 201));

    const { result } = await renderHook(
      () => ({
        api: useAuthenticatedApi(),
        session: useSession(),
      }),
      { wrapper }
    );

    await act(async () => {
      await result.current.session.signIn('user', 'pass');
    });

    let postResult: { id: string; content: string } | undefined;
    await act(async () => {
      postResult = await result.current.api.request<{
        id: string;
        content: string;
      }>('posts', '/api/v1/posts', {
        method: 'POST',
        body: { content: 'hello' },
      });
    });

    expect(postResult).toEqual({ id: 'p1', content: 'hello' });
    expect(fetchSpy).toHaveBeenLastCalledWith(
      'http://localhost:8001/api/v1/posts',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer my-token',
        }),
      })
    );
  });

  it('invalidates session if server returns 401 on authenticated call', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'revoked-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            type: 'https://udesa-x.dev/problems/invalid-access-token',
            status: 401,
            title: 'Invalid access token',
            detail: 'Token was revoked',
          },
          401,
          { 'content-type': 'application/problem+json' }
        )
      );

    const { result } = await renderHook(
      () => ({
        api: useAuthenticatedApi(),
        session: useSession(),
      }),
      { wrapper }
    );

    await act(async () => {
      await result.current.session.signIn('user', 'pass');
    });

    expect(result.current.session.session).not.toBeNull();

    await act(async () => {
      await expect(
        result.current.api.request('posts', '/api/v1/posts', { method: 'GET' })
      ).rejects.toMatchObject({
        status: 401,
        code: 'invalid-access-token',
      });
    });

    expect(result.current.session.session).toBeNull();
  });
});

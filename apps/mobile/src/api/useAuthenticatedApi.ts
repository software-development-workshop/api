import { useCallback } from 'react';
import { useSession } from '../auth/SessionContext';
import { requestJson, RequestJsonOptions, ServiceName, ApiError } from './http';

export function useAuthenticatedApi() {
  const { session, invalidate, getSession } = useSession();

  const request = useCallback(
    async <T>(
      service: ServiceName,
      path: string,
      options: Omit<RequestJsonOptions, 'token'>
    ): Promise<T> => {
      const activeSession = getSession();

      if (!activeSession || Date.now() >= activeSession.expiresAt) {
        invalidate();
        throw new ApiError(
          401,
          'invalid-access-token',
          'Tu sesión no es válida o ha expirado.'
        );
      }

      const activeToken = activeSession.accessToken;

      try {
        const result = await requestJson<T>(service, path, {
          ...options,
          token: activeToken,
        });

        const currentSession = getSession();
        if (
          currentSession !== activeSession ||
          Date.now() >= activeSession.expiresAt
        ) {
          throw new ApiError(
            401,
            'invalid-access-token',
            'La sesión cambió durante la solicitud.'
          );
        }

        return result;
      } catch (error) {
        if (
          error instanceof ApiError &&
          (error.status === 401 || error.code === 'invalid-access-token')
        ) {
          const currentSession = getSession();
          if (currentSession === activeSession) {
            invalidate();
          }
        }
        throw error;
      }
    },
    [invalidate, getSession]
  );

  return { request, session };
}

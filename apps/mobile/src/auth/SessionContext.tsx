import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { requestJson, ApiError } from '../api/http';
import { SessionData, SessionContextValue, RawSessionResponse } from './types';

const SessionContext = createContext<SessionContextValue | null>(null);

export function validateSessionResponse(data: RawSessionResponse): {
  accessToken: string;
  expiresIn: number;
} {
  if (
    !data ||
    typeof data.access_token !== 'string' ||
    data.access_token.trim().length === 0
  ) {
    throw new ApiError(
      500,
      'invalid-session-response',
      'El servidor devolvió un token de acceso inválido.'
    );
  }

  if (
    typeof data.token_type !== 'string' ||
    data.token_type.trim().toLowerCase() !== 'bearer'
  ) {
    throw new ApiError(
      500,
      'invalid-session-response',
      'El servidor devolvió un tipo de token no soportado.'
    );
  }

  if (
    typeof data.expires_in !== 'number' ||
    !Number.isFinite(data.expires_in) ||
    data.expires_in <= 0
  ) {
    throw new ApiError(
      500,
      'invalid-session-response',
      'El servidor devolvió un tiempo de expiración inválido.'
    );
  }

  return {
    accessToken: data.access_token,
    expiresIn: data.expires_in,
  };
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionData | null>(null);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  const sessionRef = useRef<SessionData | null>(null);
  const generationRef = useRef(0);
  const establishedSessionVersionRef = useRef(0);

  const activeSignInRef = useRef<{
    promise: Promise<void>;
    identifier: string;
    generation: number;
  } | null>(null);

  const activeSignOutRef = useRef<{
    promise: Promise<{ revoked: boolean }>;
    generation: number;
  } | null>(null);

  const invalidate = useCallback(() => {
    generationRef.current += 1;
    sessionRef.current = null;
    setSession(null);
  }, []);

  const getSession = useCallback(() => {
    return sessionRef.current;
  }, []);

  const clearSessionNotice = useCallback(() => {
    setSessionNotice(null);
  }, []);

  const signIn = useCallback(
    async (identifier: string, password: string): Promise<void> => {
      const currentActive = activeSignInRef.current;
      if (
        currentActive &&
        currentActive.identifier === identifier &&
        currentActive.generation === generationRef.current
      ) {
        return currentActive.promise;
      }

      const operationGen = generationRef.current + 1;
      generationRef.current = operationGen;

      let signInPromise!: Promise<void>;
      signInPromise = (async () => {
        try {
          const rawResponse = await requestJson<RawSessionResponse>(
            'accounts',
            '/api/v1/sessions',
            {
              method: 'POST',
              body: { identifier, password },
            }
          );

          const { accessToken, expiresIn } =
            validateSessionResponse(rawResponse);

          if (generationRef.current !== operationGen) {
            return;
          }

          const newSession: SessionData = {
            accessToken,
            expiresAt: Date.now() + expiresIn * 1000,
          };

          sessionRef.current = newSession;
          establishedSessionVersionRef.current += 1;
          setSession(newSession);
          setSessionNotice(null);
        } finally {
          if (activeSignInRef.current?.promise === signInPromise) {
            activeSignInRef.current = null;
          }
        }
      })();

      activeSignInRef.current = {
        promise: signInPromise,
        identifier,
        generation: operationGen,
      };

      return signInPromise;
    },
    []
  );

  const signOut = useCallback(async (): Promise<{ revoked: boolean }> => {
    const targetSession = sessionRef.current;
    if (!targetSession) {
      const pending = activeSignOutRef.current;
      if (pending?.generation === generationRef.current) {
        return pending.promise;
      }
      invalidate();
      return { revoked: false };
    }

    const tokenToRevoke = targetSession.accessToken;
    const sessionVersion = establishedSessionVersionRef.current;

    const operationGen = generationRef.current + 1;
    generationRef.current = operationGen;
    sessionRef.current = null;
    setSession(null);

    const signOutPromise = (async () => {
      let revoked = false;
      try {
        await requestJson('accounts', '/api/v1/sessions/logout', {
          method: 'POST',
          token: tokenToRevoke,
        });
        revoked = true;
      } catch {
        revoked = false;
      }

      if (establishedSessionVersionRef.current === sessionVersion) {
        if (!revoked) {
          setSessionNotice(
            'Saliste de este dispositivo. No pudimos confirmar el cierre de sesión en el servidor'
          );
        } else {
          setSessionNotice(null);
        }
      }

      return { revoked };
    })();

    activeSignOutRef.current = {
      promise: signOutPromise,
      generation: operationGen,
    };

    signOutPromise.finally(() => {
      if (activeSignOutRef.current?.promise === signOutPromise) {
        activeSignOutRef.current = null;
      }
    });

    return signOutPromise;
  }, [invalidate]);

  useEffect(() => {
    if (!session) {
      return;
    }

    const targetSession = session;

    const checkExpiry = () => {
      if (
        sessionRef.current === targetSession &&
        Date.now() >= targetSession.expiresAt
      ) {
        invalidate();
      }
    };

    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === 'active') {
        checkExpiry();
      }
    };

    const subscription = AppState.addEventListener(
      'change',
      handleAppStateChange
    );

    const remainingTime = targetSession.expiresAt - Date.now();
    let timerId: ReturnType<typeof setTimeout> | null = null;
    if (remainingTime <= 0) {
      checkExpiry();
    } else {
      timerId = setTimeout(() => {
        checkExpiry();
      }, remainingTime);
    }

    return () => {
      subscription.remove();
      if (timerId) {
        clearTimeout(timerId);
      }
    };
  }, [session, invalidate]);

  const value: SessionContextValue = {
    session,
    signIn,
    signOut,
    invalidate,
    getSession,
    sessionNotice,
    clearSessionNotice,
  };

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}

export interface SessionData {
  accessToken: string;
  expiresAt: number;
}

export interface RawSessionResponse {
  access_token: unknown;
  token_type: unknown;
  expires_in: unknown;
}

export interface SessionContextValue {
  session: SessionData | null;
  signIn: (identifier: string, password: string) => Promise<void>;
  signOut: () => Promise<{ revoked: boolean }>;
  invalidate: () => void;
  getSession: () => SessionData | null;
  sessionNotice: string | null;
  clearSessionNotice: () => void;
}

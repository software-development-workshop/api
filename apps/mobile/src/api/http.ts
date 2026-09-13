export type ServiceName = 'accounts' | 'posts';

export interface RequestJsonOptions {
  method: 'GET' | 'POST';
  body?: unknown;
  token?: string;
}

const ERROR_MESSAGES_ES: Record<string, string> = {
  'invalid-credentials': 'Email, usuario o contraseña incorrectos.',
  'unverified-account':
    'Tu cuenta aún no fue verificada. Revisá tu casilla de correo.',
  'suspended-account': 'Esta cuenta ha sido suspendida.',
  'account-temporarily-locked':
    'Cuenta bloqueada temporalmente por demasiados intentos fallidos. Intentá más tarde.',
  'invalid-access-token': 'Tu sesión no es válida o ha expirado.',
  'validation-error': 'Los datos ingresados no son válidos.',
  'network-error':
    'No pudimos conectar con el servidor. Comprobá tu conexión a internet e intentá nuevamente.',
  'timeout-error':
    'La solicitud tardó demasiado tiempo. Comprobá tu conexión e intentá nuevamente.',
  'malformed-response': 'Respuesta inválida del servidor.',
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function extractErrorCode(slugOrType: unknown): string {
  if (typeof slugOrType !== 'string' || !slugOrType.trim()) {
    return 'http-error';
  }
  const parts = slugOrType.trim().split('/');
  return parts[parts.length - 1] || 'http-error';
}

export function mapErrorMessage(code: string, status?: number): string {
  if (ERROR_MESSAGES_ES[code]) {
    return ERROR_MESSAGES_ES[code];
  }
  if (status === 401) {
    return ERROR_MESSAGES_ES['invalid-access-token'];
  }
  if (status === 403) {
    return ERROR_MESSAGES_ES['suspended-account'];
  }
  return 'Ocurrió un error inesperado. Por favor, intentá nuevamente.';
}

export function getBaseUrl(service: ServiceName): string {
  const envUrl =
    service === 'accounts'
      ? process.env.EXPO_PUBLIC_ACCOUNTS_API_URL
      : process.env.EXPO_PUBLIC_POSTS_API_URL;

  if (!envUrl || !envUrl.trim()) {
    const varName =
      service === 'accounts'
        ? 'EXPO_PUBLIC_ACCOUNTS_API_URL'
        : 'EXPO_PUBLIC_POSTS_API_URL';
    throw new ApiError(
      0,
      'configuration-error',
      `Configuración de API faltante: la variable ${varName} no está definida.`
    );
  }

  const trimmed = envUrl.trim();
  try {
    const parsed = new URL(trimmed);
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      throw new Error('Invalid protocol');
    }
  } catch {
    throw new ApiError(
      0,
      'configuration-error',
      `Configuración de API inválida: la URL configurada para ${service} no es válida.`
    );
  }

  return trimmed.replace(/\/+$/, '');
}

export async function requestJson<T>(
  service: ServiceName,
  path: string,
  options: RequestJsonOptions
): Promise<T> {
  const baseUrl = getBaseUrl(service);
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const fullUrl = `${baseUrl}${normalizedPath}`;

  const headers: Record<string, string> = {
    Accept: 'application/json, application/problem+json',
  };

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  let bodyContent: string | undefined;
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json; charset=utf-8';
    bodyContent = JSON.stringify(options.body);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, 10000);

  try {
    const response = await fetch(fullUrl, {
      method: options.method,
      headers,
      body: bodyContent,
      signal: controller.signal,
    });

    if (response.status === 204) {
      return undefined as unknown as T;
    }

    const contentType = response.headers.get('content-type') || '';
    const isJson =
      contentType.includes('application/json') ||
      contentType.includes('application/problem+json');

    let rawText = '';
    try {
      rawText = await response.text();
    } catch (readErr: unknown) {
      const code =
        controller.signal.aborted ||
        (readErr instanceof Error && readErr.name === 'AbortError')
          ? 'timeout-error'
          : 'network-error';
      // A truncated body does not undo an HTTP rejection already received.
      throw new ApiError(
        response.ok ? 0 : response.status,
        code,
        ERROR_MESSAGES_ES[code]
      );
    }

    let parsedData: unknown = null;
    let parseSucceeded = false;
    if (rawText.trim().length > 0) {
      try {
        parsedData = JSON.parse(rawText);
        parseSucceeded = true;
      } catch {
        parseSucceeded = false;
      }
    }

    if (!response.ok) {
      let code = 'http-error';
      if (parseSucceeded && parsedData && typeof parsedData === 'object') {
        const problem = parsedData as Record<string, unknown>;
        if (typeof problem.type === 'string') {
          code = extractErrorCode(problem.type);
        }
      }
      if (code === 'http-error' && response.status === 401) {
        code = 'invalid-credentials';
      }

      const friendlyMessage = mapErrorMessage(code, response.status);
      throw new ApiError(response.status, code, friendlyMessage);
    }

    if (!parseSucceeded || !isJson) {
      throw new ApiError(
        response.status,
        'malformed-response',
        ERROR_MESSAGES_ES['malformed-response']
      );
    }

    return parsedData as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    if (
      controller.signal.aborted ||
      (err instanceof Error && err.name === 'AbortError')
    ) {
      throw new ApiError(
        0,
        'timeout-error',
        ERROR_MESSAGES_ES['timeout-error']
      );
    }
    throw new ApiError(0, 'network-error', ERROR_MESSAGES_ES['network-error']);
  } finally {
    clearTimeout(timeoutId);
  }
}

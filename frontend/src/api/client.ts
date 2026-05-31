import { env } from '@/config/env';

export type AuthTokenGetter = () => Promise<string | null> | string | null;

type ApiRequestOptions = RequestInit & {
  auth?: boolean;
  token?: string | null;
};

let authTokenGetter: AuthTokenGetter | undefined;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function setAuthTokenGetter(getter: AuthTokenGetter) {
  authTokenGetter = getter;
}

export async function apiRequest<T>(
  path: string,
  { auth = true, token, ...options }: ApiRequestOptions = {},
): Promise<T> {
  const url = path.startsWith('http')
    ? path
    : `${env.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = new Headers(options.headers);

  headers.set('Accept', 'application/json');

  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (auth) {
    const resolvedToken = token ?? (await authTokenGetter?.()) ?? null;

    if (resolvedToken) {
      headers.set('Authorization', `Bearer ${resolvedToken}`);
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throw new ApiError(response.statusText || 'API request failed', response.status, payload);
  }

  return payload as T;
}

async function parseResponse(response: Response): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

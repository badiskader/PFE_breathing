type EnvValue = string | undefined;

function readEnv(name: string): EnvValue {
  return process.env[name];
}

function readBoolean(name: string, fallback: boolean): boolean {
  const value = readEnv(name);

  if (value === undefined) {
    return fallback;
  }

  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
}

export const env = {
  apiBaseUrl: readEnv('EXPO_PUBLIC_API_BASE_URL') ?? 'http://localhost:8080',
  useMocks: readBoolean('EXPO_PUBLIC_USE_MOCKS', false),
  mockAuth: readBoolean('EXPO_PUBLIC_MOCK_AUTH', true),
  mockAnalytics: readBoolean('EXPO_PUBLIC_MOCK_ANALYTICS', true),
  mockNotifications: readBoolean('EXPO_PUBLIC_MOCK_NOTIFICATIONS', true),
  mockWeather: readBoolean('EXPO_PUBLIC_MOCK_WEATHER', true),
} as const;

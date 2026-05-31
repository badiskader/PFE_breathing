import { env } from '@/config/env';

export type MockScope = 'auth' | 'analytics' | 'notifications' | 'weather';

const scopeFlags: Record<MockScope, boolean> = {
  analytics: env.mockAnalytics,
  auth: env.mockAuth,
  notifications: env.mockNotifications,
  weather: env.mockWeather,
};

export function shouldUseMock(scope?: MockScope): boolean {
  if (env.useMocks) {
    return true;
  }

  return scope ? scopeFlags[scope] : false;
}

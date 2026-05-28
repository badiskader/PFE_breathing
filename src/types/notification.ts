import type { AnalyticsRange } from './analytics';

export type NotificationType =
  | 'aqi_alert'
  | 'forecast_alert'
  | 'recommendation_alert'
  | 'system'
  | 'daily_summary';

export type NotificationSeverity = 'safe' | 'caution' | 'avoid' | 'danger' | 'info';

export type NotificationTargetScreen = 'MyAir' | 'Map' | 'Chat' | 'Profile' | 'Analytics';

export type AppNotification = {
  notification_id: string;
  type: NotificationType;
  title: string;
  body: string;
  severity: NotificationSeverity;
  sensor_id?: string;
  created_at: string;
  read: boolean;
  data: {
    screen: NotificationTargetScreen;
    sensor_id?: string;
    range?: AnalyticsRange;
  };
};

export type NotificationsResponse = {
  notifications: AppNotification[];
};

export type QuietHours = {
  enabled: boolean;
  start: string;
  end: string;
};

export type NotificationSettings = {
  aqi_alerts_enabled: boolean;
  forecast_alerts_enabled: boolean;
  recommendation_alerts_enabled: boolean;
  daily_summary_enabled: boolean;
  language: 'fr' | 'en';
  quiet_hours: QuietHours;
};

export type RegisterPushTokenRequest = {
  expo_push_token: string;
  platform: 'ios' | 'android' | 'web';
  device_id?: string;
  app_version: string;
};

export type DeletePushTokenRequest = {
  expo_push_token: string;
};

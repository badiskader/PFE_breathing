import type { NotificationSettings, NotificationsResponse } from '@/types';

export const mockNotificationsResponse = {
  notifications: [
    {
      notification_id: 'notif_001',
      type: 'aqi_alert',
      title: 'Air quality alert',
      body: 'PM2.5 is expected to rise this evening. Limit intense outdoor activity.',
      severity: 'caution',
      sensor_id: 'AQ_CST_01',
      created_at: '2026-05-21T19:00:00Z',
      read: false,
      data: {
        screen: 'MyAir',
        sensor_id: 'AQ_CST_01',
      },
    },
    {
      notification_id: 'notif_002',
      type: 'forecast_alert',
      title: 'Forecast peak',
      body: 'AQI may reach 105 overnight near your selected station.',
      severity: 'avoid',
      sensor_id: 'AQ_CST_01',
      created_at: '2026-05-21T18:30:00Z',
      read: false,
      data: {
        screen: 'Map',
        sensor_id: 'AQ_CST_01',
      },
    },
    {
      notification_id: 'notif_003',
      type: 'daily_summary',
      title: 'Morning briefing',
      body: 'Good air quality is expected early, with moderate levels later in the day.',
      severity: 'info',
      created_at: '2026-05-21T07:00:00Z',
      read: true,
      data: {
        screen: 'Analytics',
        range: '24h',
      },
    },
  ],
} satisfies NotificationsResponse;

export const mockNotificationSettings = {
  aqi_alerts_enabled: true,
  forecast_alerts_enabled: true,
  recommendation_alerts_enabled: true,
  daily_summary_enabled: true,
  language: 'fr',
  quiet_hours: {
    enabled: true,
    start: '22:00',
    end: '07:00',
  },
} satisfies NotificationSettings;

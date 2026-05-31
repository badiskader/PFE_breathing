import { useTranslation } from 'react-i18next';

import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

export function NotificationSettingsScreen() {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      body={t('placeholders.notificationSettings.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.notificationSettings')}
    />
  );
}

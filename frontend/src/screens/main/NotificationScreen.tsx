import { useTranslation } from 'react-i18next';

import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

export function NotificationScreen() {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      body={t('placeholders.notifications.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.notifications')}
    />
  );
}

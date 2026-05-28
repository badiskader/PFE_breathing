import { useTranslation } from 'react-i18next';

import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

export function ChatSessionsScreen() {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      body={t('placeholders.chatSessions.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.chatSessions')}
    />
  );
}

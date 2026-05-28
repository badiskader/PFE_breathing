import { useTranslation } from 'react-i18next';

import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

export function LanguageSettingsScreen() {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      body={t('placeholders.languageSettings.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.languageSettings')}
    />
  );
}

import { useTranslation } from 'react-i18next';

import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

export function EditProfileScreen() {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      body={t('placeholders.editProfile.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.editProfile')}
    />
  );
}

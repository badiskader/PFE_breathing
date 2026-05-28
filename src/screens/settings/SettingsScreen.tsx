import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useTranslation } from 'react-i18next';

import type { MainStackParamList } from '@/navigation/types';
import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

export function SettingsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<MainStackParamList>>();
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      actions={[
        {
          label: t('actions.language'),
          onPress: () => navigation.navigate('LanguageSettings'),
        },
        {
          label: t('actions.notificationSettings'),
          onPress: () => navigation.navigate('NotificationSettings'),
          tone: 'secondary',
        },
      ]}
      body={t('placeholders.settings.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.settings')}
    />
  );
}

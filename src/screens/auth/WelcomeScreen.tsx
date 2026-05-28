import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useTranslation } from 'react-i18next';

import type { AuthStackParamList, RootStackParamList } from '@/navigation/types';
import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

type Props = NativeStackScreenProps<AuthStackParamList, 'Welcome'>;
type RootNavigation = NativeStackScreenProps<RootStackParamList>['navigation'];

export function WelcomeScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const rootNavigation = navigation.getParent<RootNavigation>();

  return (
    <PlaceholderScreen
      actions={[
        {
          label: t('actions.enterDemo'),
          onPress: () => rootNavigation?.replace('Main'),
        },
        {
          label: t('actions.login'),
          onPress: () => navigation.navigate('Login'),
          tone: 'secondary',
        },
        {
          label: t('actions.register'),
          onPress: () => navigation.navigate('Register'),
          tone: 'secondary',
        },
      ]}
      body={t('placeholders.welcome.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('placeholders.welcome.title')}
    />
  );
}

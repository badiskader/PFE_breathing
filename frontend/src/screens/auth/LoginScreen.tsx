import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useTranslation } from 'react-i18next';

import type { AuthStackParamList, RootStackParamList } from '@/navigation/types';
import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

type Props = NativeStackScreenProps<AuthStackParamList, 'Login'>;
type RootNavigation = NativeStackScreenProps<RootStackParamList>['navigation'];

export function LoginScreen({ navigation }: Props) {
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
          label: t('actions.createAccount'),
          onPress: () => navigation.navigate('Register'),
          tone: 'secondary',
        },
      ]}
      body={t('placeholders.login.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('placeholders.login.title')}
    />
  );
}

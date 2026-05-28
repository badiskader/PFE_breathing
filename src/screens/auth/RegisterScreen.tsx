import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useTranslation } from 'react-i18next';

import type { AuthStackParamList } from '@/navigation/types';
import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

type Props = NativeStackScreenProps<AuthStackParamList, 'Register'>;

export function RegisterScreen({ navigation }: Props) {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      actions={[
        {
          label: t('actions.continue'),
          onPress: () => navigation.navigate('OnboardingHealthProfile'),
        },
        {
          label: t('actions.login'),
          onPress: () => navigation.navigate('Login'),
          tone: 'secondary',
        },
      ]}
      body={t('placeholders.register.body')}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('placeholders.register.title')}
    />
  );
}

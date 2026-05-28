import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useTranslation } from 'react-i18next';

import type { MainStackParamList } from '@/navigation/types';
import { PlaceholderScreen } from '@/screens/placeholders/PlaceholderScreen';

type Props = NativeStackScreenProps<MainStackParamList, 'StationDetails'>;

export function StationDetailsScreen({ route }: Props) {
  const { t } = useTranslation();

  return (
    <PlaceholderScreen
      body={t('placeholders.stationDetails.body', {
        sensorId: route.params?.sensorId ?? 'AQ_CST_01',
      })}
      eyebrow={t('placeholders.navigationOnly')}
      title={t('routes.stationDetails')}
    />
  );
}

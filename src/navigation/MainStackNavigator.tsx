import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useTranslation } from 'react-i18next';

import { ChatSessionsScreen } from '@/screens/main/ChatSessionsScreen';
import { EditProfileScreen } from '@/screens/main/EditProfileScreen';
import { NotificationScreen } from '@/screens/main/NotificationScreen';
import { StationDetailsScreen } from '@/screens/main/StationDetailsScreen';
import { LanguageSettingsScreen } from '@/screens/settings/LanguageSettingsScreen';
import { NotificationSettingsScreen } from '@/screens/settings/NotificationSettingsScreen';
import { SettingsScreen } from '@/screens/settings/SettingsScreen';
import { colors } from '@/theme';

import { MainTabNavigator } from './MainTabNavigator';
import type { MainStackParamList } from './types';

const Stack = createNativeStackNavigator<MainStackParamList>();

export function MainStackNavigator() {
  const { t } = useTranslation();

  return (
    <Stack.Navigator
      screenOptions={{
        contentStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTintColor: colors.textPrimary,
        headerTitleStyle: {
          color: colors.textPrimary,
          fontWeight: '800',
        },
      }}
    >
      <Stack.Screen
        component={MainTabNavigator}
        name="MainTabs"
        options={{ headerShown: false }}
      />
      <Stack.Screen
        component={EditProfileScreen}
        name="EditProfile"
        options={{ title: t('routes.editProfile') }}
      />
      <Stack.Screen
        component={StationDetailsScreen}
        name="StationDetails"
        options={{ title: t('routes.stationDetails') }}
      />
      <Stack.Screen
        component={ChatSessionsScreen}
        name="ChatSessions"
        options={{ title: t('routes.chatSessions') }}
      />
      <Stack.Screen
        component={NotificationScreen}
        name="Notification"
        options={{ title: t('routes.notifications') }}
      />
      <Stack.Screen
        component={NotificationSettingsScreen}
        name="NotificationSettings"
        options={{ title: t('routes.notificationSettings') }}
      />
      <Stack.Screen
        component={SettingsScreen}
        name="Settings"
        options={{ title: t('routes.settings') }}
      />
      <Stack.Screen
        component={LanguageSettingsScreen}
        name="LanguageSettings"
        options={{ title: t('routes.languageSettings') }}
      />
    </Stack.Navigator>
  );
}

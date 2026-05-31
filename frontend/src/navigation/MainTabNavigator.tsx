import { Ionicons } from '@expo/vector-icons';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import type { ComponentProps } from 'react';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AnalyticsScreen } from '@/screens/main/AnalyticsScreen';
import { ChatScreen } from '@/screens/main/ChatScreen';
import { MapScreen } from '@/screens/main/MapScreen';
import { MyAirScreen } from '@/screens/main/MyAirScreen';
import { ProfileScreen } from '@/screens/main/ProfileScreen';
import { colors } from '@/theme';

import type { MainTabParamList } from './types';

const Tab = createBottomTabNavigator<MainTabParamList>();

type IoniconName = ComponentProps<typeof Ionicons>['name'];

const tabIcons: Record<keyof MainTabParamList, { focused: IoniconName; idle: IoniconName }> = {
  Analytics: { focused: 'pulse', idle: 'pulse-outline' },
  Chat: { focused: 'chatbox', idle: 'chatbox-outline' },
  Map: { focused: 'globe', idle: 'globe-outline' },
  MyAir: { focused: 'heart', idle: 'heart-outline' },
  Profile: { focused: 'person', idle: 'person-outline' },
};

const tabLabels: Record<keyof MainTabParamList, string> = {
  Analytics: 'tabs.analytics',
  Chat: 'tabs.chat',
  Map: 'tabs.map',
  MyAir: 'tabs.myAir',
  Profile: 'tabs.profile',
};

export function MainTabNavigator() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const bottomInset = Math.max(insets.bottom, 0);
  const tabBarBottomPadding = bottomInset > 0 ? bottomInset : 4;
  const tabBarHeight = 56 + tabBarBottomPadding;

  return (
    <Tab.Navigator
      initialRouteName="MyAir"
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.primaryBlue,
        tabBarIcon: ({ color, focused, size }) => {
          const icon = tabIcons[route.name][focused ? 'focused' : 'idle'];
          return <Ionicons color={color} name={icon} size={size} />;
        },
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabel: t(tabLabels[route.name]),
        tabBarLabelStyle: {
          fontSize: 14,
          fontWeight: focusedLabelWeight(route.name),
          marginTop: 2,
        },
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          height: tabBarHeight,
          paddingBottom: tabBarBottomPadding,
          paddingTop: 4,
        },
      })}
    >
      <Tab.Screen component={MyAirScreen} name="MyAir" />
      <Tab.Screen component={MapScreen} name="Map" />
      <Tab.Screen component={ChatScreen} name="Chat" />
      <Tab.Screen component={AnalyticsScreen} name="Analytics" />
      <Tab.Screen component={ProfileScreen} name="Profile" />
    </Tab.Navigator>
  );
}

function focusedLabelWeight(_routeName: keyof MainTabParamList) {
  return '600' as const;
}

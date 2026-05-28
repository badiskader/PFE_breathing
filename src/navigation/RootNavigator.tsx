import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { AuthNavigator } from './AuthNavigator';
import { MainStackNavigator } from './MainStackNavigator';
import { navigationTheme } from './navigationTheme';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();
const START_IN_DEMO_APP = true;

export function RootNavigator() {
  return (
    <NavigationContainer theme={navigationTheme}>
      <Stack.Navigator
        initialRouteName={START_IN_DEMO_APP ? 'Main' : 'Auth'}
        screenOptions={{ headerShown: false }}
      >
        <Stack.Screen component={AuthNavigator} name="Auth" />
        <Stack.Screen component={MainStackNavigator} name="Main" />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

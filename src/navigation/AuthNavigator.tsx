import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { LoginScreen } from '@/screens/auth/LoginScreen';
import { OnboardingHealthProfileScreen } from '@/screens/auth/OnboardingHealthProfileScreen';
import { RegisterScreen } from '@/screens/auth/RegisterScreen';
import { WelcomeScreen } from '@/screens/auth/WelcomeScreen';

import type { AuthStackParamList } from './types';

const Stack = createNativeStackNavigator<AuthStackParamList>();

export function AuthNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen component={WelcomeScreen} name="Welcome" />
      <Stack.Screen component={LoginScreen} name="Login" />
      <Stack.Screen component={RegisterScreen} name="Register" />
      <Stack.Screen
        component={OnboardingHealthProfileScreen}
        name="OnboardingHealthProfile"
      />
    </Stack.Navigator>
  );
}

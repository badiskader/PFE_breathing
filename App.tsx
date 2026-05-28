import { StatusBar } from 'expo-status-bar';

import './src/i18n';

import { RootNavigator } from './src/navigation/RootNavigator';
import { AppProviders } from './src/providers/AppProviders';

export default function App() {
  return (
    <AppProviders>
      <RootNavigator />
      <StatusBar style="dark" />
    </AppProviders>
  );
}

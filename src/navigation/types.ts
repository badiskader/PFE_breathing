export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
};

export type AuthStackParamList = {
  Welcome: undefined;
  Login: undefined;
  Register: undefined;
  OnboardingHealthProfile: undefined;
};

export type MainTabParamList = {
  MyAir: undefined;
  Map: undefined;
  Chat: undefined;
  Analytics: undefined;
  Profile: undefined;
};

export type MainStackParamList = {
  MainTabs: undefined;
  EditProfile: undefined;
  StationDetails: { sensorId?: string } | undefined;
  ChatSessions: undefined;
  Notification: undefined;
  NotificationSettings: undefined;
  Settings: undefined;
  LanguageSettings: undefined;
};

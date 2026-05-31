# AirPulse Mobile

React Native / Expo frontend for the AirPulse AI-IoT air quality monitoring and personalized recommendation prototype.

## Development

1. Copy `.env.example` to `.env`.
2. Set `EXPO_PUBLIC_API_BASE_URL` to your backend LAN URL, for example `http://192.168.1.20:8080`.
3. Start the app:

```bash
npm run start
```

The backend currently exposes real AQI, prediction, recommendation, onboarding, and chat endpoints. Auth, analytics, notifications, and weather values are scaffolded behind mock flags until the backend exposes them.

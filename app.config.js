const fs = require('fs');
const path = require('path');

const appJson = require('./app.json');

function readDotEnvValue(name) {
  if (process.env[name]) {
    return process.env[name];
  }

  const envPath = path.join(__dirname, '.env');

  if (!fs.existsSync(envPath)) {
    return undefined;
  }

  const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);

  for (const line of lines) {
    const trimmedLine = line.trim();

    if (!trimmedLine || trimmedLine.startsWith('#')) {
      continue;
    }

    const separatorIndex = trimmedLine.indexOf('=');

    if (separatorIndex === -1) {
      continue;
    }

    const key = trimmedLine.slice(0, separatorIndex).trim();
    const value = trimmedLine.slice(separatorIndex + 1).trim();

    if (key === name) {
      return value.replace(/^["']|["']$/g, '');
    }
  }

  return undefined;
}

const googleMapsApiKey =
  readDotEnvValue('GOOGLE_MAPS_API_KEY') ?? readDotEnvValue('EXPO_PUBLIC_GOOGLE_MAPS_API_KEY') ?? '';

module.exports = () => {
  const baseConfig = appJson.expo;
  const existingPlugins = baseConfig.plugins ?? [];
  const pluginsWithoutMaps = existingPlugins.filter((plugin) => {
    if (Array.isArray(plugin)) {
      return plugin[0] !== 'react-native-maps';
    }

    return plugin !== 'react-native-maps';
  });

  return {
    ...baseConfig,
    android: {
      ...baseConfig.android,
      config: {
        ...(baseConfig.android?.config ?? {}),
        googleMaps: {
          ...(baseConfig.android?.config?.googleMaps ?? {}),
          apiKey: googleMapsApiKey,
        },
      },
    },
    extra: {
      ...(baseConfig.extra ?? {}),
      googleMapsApiKeyConfigured: Boolean(googleMapsApiKey),
    },
    ios: {
      ...baseConfig.ios,
      config: {
        ...(baseConfig.ios?.config ?? {}),
        googleMapsApiKey,
      },
    },
    plugins: [
      ...pluginsWithoutMaps,
      [
        'react-native-maps',
        {
          androidGoogleMapsApiKey: googleMapsApiKey,
          iosGoogleMapsApiKey: googleMapsApiKey,
        },
      ],
    ],
  };
};

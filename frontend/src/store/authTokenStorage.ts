import * as SecureStore from 'expo-secure-store';

const AUTH_TOKEN_KEY = 'airpulse.auth.token';

export const authTokenStorage = {
  async clearToken() {
    await SecureStore.deleteItemAsync(AUTH_TOKEN_KEY);
  },
  async getToken() {
    return SecureStore.getItemAsync(AUTH_TOKEN_KEY);
  },
  async setToken(token: string) {
    await SecureStore.setItemAsync(AUTH_TOKEN_KEY, token);
  },
};

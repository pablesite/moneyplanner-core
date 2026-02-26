import { computed, ref } from 'vue';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const accessToken = ref<string | null>(null);
const refreshToken = ref<string | null>(null);
let hydrated = false;

function hydrateFromStorage() {
  if (hydrated) return;
  hydrated = true;
  accessToken.value = localStorage.getItem(ACCESS_TOKEN_KEY);
  refreshToken.value = localStorage.getItem(REFRESH_TOKEN_KEY);
}

export const hasAccessToken = computed(() => {
  hydrateFromStorage();
  return !!accessToken.value;
});

export function getAccessToken() {
  hydrateFromStorage();
  return accessToken.value;
}

export function getRefreshToken() {
  hydrateFromStorage();
  return refreshToken.value;
}

export function setAccessToken(token: string) {
  hydrateFromStorage();
  accessToken.value = token;
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function setRefreshToken(token: string) {
  hydrateFromStorage();
  refreshToken.value = token;
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

export function clearAuthTokens() {
  hydrateFromStorage();
  accessToken.value = null;
  refreshToken.value = null;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

import { api } from '@/lib/api';

export type LoginPayload = {
  username: string;
  password: string;
};

export const authApi = {
  login(payload: LoginPayload) {
    return api.post('/api/auth/token/', payload);
  },
};

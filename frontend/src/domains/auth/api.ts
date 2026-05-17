import type { AxiosResponse } from 'axios';
import { api } from '@/lib/api';

export type LoginPayload = {
  username: string;
  password: string;
};

export type RegisterPayload = {
  username: string;
  password: string;
  password_confirm: string;
};

export type LoginResponse = {
  access: string;
  refresh?: string;
};

export type AuthApiAdapter = {
  login(payload: LoginPayload): Promise<AxiosResponse<LoginResponse>>;
  register(payload: RegisterPayload): Promise<AxiosResponse<LoginResponse>>;
  validateSession(): Promise<AxiosResponse<{ base_currency?: string }>>;
  logout(refresh: string): Promise<AxiosResponse<void>>;
};

export const coreAuthApi: AuthApiAdapter = {
  login(payload: LoginPayload) {
    return api.post<LoginResponse>('/api/auth/token/', payload);
  },
  register(payload: RegisterPayload) {
    return api.post<LoginResponse>('/api/auth/register/', payload);
  },
  validateSession() {
    return api.get<{ base_currency?: string }>('/api/auth/me/');
  },
  logout(refresh: string) {
    return api.post<void>('/api/auth/logout/', { refresh });
  },
};

export const authApi: AuthApiAdapter = coreAuthApi;

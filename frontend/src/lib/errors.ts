export function toApiErrorMessage(error: unknown): string {
  const maybe = error as { response?: { data?: unknown }; message?: string } | null | undefined;
  if (maybe?.response?.data) return JSON.stringify(maybe.response.data);
  if (maybe?.message) return maybe.message;
  return 'Error';
}

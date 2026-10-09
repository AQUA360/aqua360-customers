// utils/log-error.ts
// Centralized console logging for errors so every error surfaces with the same
// shape: where it happened, what was being done, and the raw error/response.
export function logError(context: string, error: any, extra: Record<string, any> = {}) {
  console.error(`[ERROR] ${context}`, {
    message: error?.message,
    status: error?.response?.status ?? error?.status,
    data: error?.response?._data ?? error?.response?.data,
    ...extra,
    error
  });
}

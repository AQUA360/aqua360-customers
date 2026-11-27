// utils/log-error.ts
// Centralized console logging for errors so every error surfaces with the same
// shape: where it happened, what was being done, and the raw error/response.
// Les contrasenyes del cos de la petició no surten mai a la consola
const SECRET_KEY = /pass(word)?|pwd|secret|token/i;

// Torna [valor sense secrets, si n'hi havia]
function redactSecrets(value: any): [any, boolean] {
  let found = false;
  const walk = (item: any): any => {
    if (Array.isArray(item)) return item.map(walk);
    if (item && typeof item === 'object' && Object.getPrototypeOf(item) === Object.prototype) {
      return Object.fromEntries(Object.entries(item).map(([key, child]) => {
        if (SECRET_KEY.test(key)) {
          found = true;
          return [key, '[redacted]'];
        }
        return [key, walk(child)];
      }));
    }
    return item;
  };
  const result = walk(value);
  return [result, found];
}

export function logError(context: string, error: any, extra: Record<string, any> = {}) {
  // L'error de $fetch porta el cos de la petició (error.options.body): si hi havia secrets,
  // no es mostra l'objecte sencer
  const [safeExtra, hadSecrets] = redactSecrets(extra);
  console.error(`[ERROR] ${context}`, {
    message: error?.message,
    status: error?.response?.status ?? error?.status,
    data: error?.response?._data ?? error?.response?.data,
    ...safeExtra,
    error: hadSecrets ? { name: error?.name, message: error?.message, stack: error?.stack } : error
  });
}

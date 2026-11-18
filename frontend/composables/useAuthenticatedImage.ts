import { onBeforeUnmount, ref, toValue, watch, type MaybeRefOrGetter } from 'vue';

/**
 * `src` per a un `<img>` d'una imatge que pot ser:
 *  - base64 o data URI: es fa servir tal qual;
 *  - URL del backend (p. ex. `/media/...`): els fitxers de `/media/` (fora dels logos)
 *    exigeixen el token i un `<img>` no pot enviar la capçalera `Authorization`, així que
 *    es descarrega amb el token i es mostra des d'una URL `blob:`;
 *  - URL d'un altre domini: tal qual, sense enviar-hi el token.
 *
 * Quan la font queda buida (p. ex. en tancar el modal) s'allibera la imatge.
 */
export function useAuthenticatedImage(source: MaybeRefOrGetter<string | null | undefined>) {
  const config = useRuntimeConfig();
  const src = ref('');
  let objectUrl: string | null = null;
  let requestId = 0;

  const release = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };

  const apiOrigin = (): string => {
    try {
      return new URL(config.public.apiHost as string, window.location.href).origin;
    } catch {
      return window.location.origin;
    }
  };

  watch(
    () => toValue(source),
    async (value) => {
      const currentRequest = ++requestId;
      release();
      src.value = '';
      if (!value || typeof value !== 'string') return;

      if (value.startsWith('data:')) {
        src.value = value;
        return;
      }
      // Només URL absolutes o rutes de /media/: un JPEG en base64 també comença per '/'
      // ('/9j/...'), així que no n'hi ha prou a mirar la barra inicial.
      const isUrl = /^https?:\/\//i.test(value) || value.startsWith('/media/');
      if (!isUrl) {
        src.value = `data:image/jpeg;base64,${value}`;
        return;
      }

      const origin = apiOrigin();
      const url = new URL(value, origin);
      if (url.origin !== origin) {
        src.value = value;
        return;
      }

      try {
        const res = await fetch(url.href, {
          headers: { Authorization: `Token ${localStorage.getItem('auth_token') || ''}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (currentRequest !== requestId) return;
        objectUrl = URL.createObjectURL(blob);
        src.value = objectUrl;
      } catch (error) {
        console.error(error);
      }
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
    requestId++;
    release();
  });

  return src;
}

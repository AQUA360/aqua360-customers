import { useToast } from 'vue-toastification';

class FileNotFoundError extends Error {
  constructor() {
    super('FILE_NOT_FOUND');
    this.name = 'FileNotFoundError';
  }
}

function openBlobInNewTab(blob: Blob): void {
  const pdfBlob = blob.type === 'application/pdf' ? blob : new Blob([blob], { type: 'application/pdf' });
  const objectUrl = URL.createObjectURL(pdfBlob);
  const newWindow = window.open(objectUrl, '_blank');

  if (!newWindow) {
    URL.revokeObjectURL(objectUrl);
    return;
  }

  const revokeWhenClosed = window.setInterval(() => {
    if (newWindow.closed) {
      URL.revokeObjectURL(objectUrl);
      window.clearInterval(revokeWhenClosed);
    }
  }, 500);
}

function downloadBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 250);
}

function filenameFromResponse(res: Response, url: string): string {
  const disposition = res.headers.get('Content-Disposition');
  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match) return decodeURIComponent(utf8Match[1]);
    const match = disposition.match(/filename="?([^";]+)"?/i);
    if (match?.[1]) return match[1];
  }
  try {
    const name = new URL(url, window.location.href).pathname.split('/').pop();
    if (name) return name;
  } catch {
    /* ignore */
  }
  return 'download';
}

export async function openAuthenticatedFileUrl(url: string, is_pdf = true): Promise<void> {
  const toast = useToast();
  const { $i18n } = useNuxtApp();

  try {
    const authToken = localStorage.getItem('auth_token') || '';
    const config = useRuntimeConfig();
    const isAlreadyResolvable = /^[a-z][a-z0-9+.-]*:/i.test(url);
    const resolvedUrl = isAlreadyResolvable ? url : `${config.public.apiHost}${url}`;
    const res = await fetch(resolvedUrl, {
      headers: { Authorization: `Token ${authToken}` },
    });

    if (!res.ok) {
      if (res.status === 404) {
        throw new FileNotFoundError();
      }
      const errText = await res.text().catch(() => '');
      throw new Error(errText || $i18n.t('common.error'));
    }

    const blob = await res.blob();
    if (is_pdf) {
      openBlobInNewTab(blob);
    } else {
      downloadBlob(blob, filenameFromResponse(res, resolvedUrl));
    }
  } catch (error) {
    console.error(error);
    if (error instanceof FileNotFoundError) {
      toast.error($i18n.t('common.file_not_found'));
    } else {
      toast.error($i18n.t('common.error'));
    }
    throw error;
  }
}

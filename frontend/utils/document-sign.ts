/**
 * Estats de `documentmanager.DocumentSign` (backend). Els valors han de coincidir
 * amb les constants `STATUS_*` del model.
 *
 * El backend també envia `status_display`, però són les etiquetes de les `STATUS_CHOICES`
 * de Django i arriben sempre en anglès; per mostrar-les cal traduir a partir del codi.
 */
export const DocumentSignStatus = {
    PENDING: 1,
    SENDED: 2,
    SIGNED: 3,
    EXPIRED: 4,
    ERROR: -1,
};

export const DocumentSignStatusLabels = {
    [DocumentSignStatus.PENDING]: 'contract_block.document_sign_status_pending',
    [DocumentSignStatus.SENDED]: 'contract_block.document_sign_status_sended',
    [DocumentSignStatus.SIGNED]: 'contract_block.document_sign_status_signed',
    [DocumentSignStatus.EXPIRED]: 'contract_block.document_sign_status_expired',
    [DocumentSignStatus.ERROR]: 'contract_block.document_sign_status_error',
};

export const DocumentSignStatusColors = {
    [DocumentSignStatus.PENDING]: 'gray',
    [DocumentSignStatus.SENDED]: 'orange',
    [DocumentSignStatus.SIGNED]: 'green',
    [DocumentSignStatus.EXPIRED]: 'yellow',
    [DocumentSignStatus.ERROR]: 'red',
};

/** El backend pot enviar el codi com a número, string o objecte `{ id }`. */
export const documentSignStatusCode = (status) => {
    if (status == null || status === '') return null;
    if (typeof status === 'object') {
        return Number(status.id ?? status.code ?? status.status);
    }
    const n = Number(status);
    return Number.isNaN(n) ? null : n;
};

export const documentSignStatusColor = (status) => DocumentSignStatusColors[documentSignStatusCode(status)] || 'gray';

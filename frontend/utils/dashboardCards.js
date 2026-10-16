/**
 * Metadades de frontend de les cards del dashboard (el catàleg i els permisos
 * venen del backend, a dashboard/cards). Els textos són a i18n:
 * home_dashboard.cards.<key>.title / .description.
 */
export const DASHBOARD_CARDS = {
  daily_activity: { icon: 'fa6-solid:list-check' },
  tasks_today: { icon: 'fa6-solid:calendar-check' },
  orders_to_validate: { icon: 'fa6-solid:clipboard-check' },
  change_meter_pending: { icon: 'fa6-solid:gauge-high' },
  reading_batches_in_progress: { icon: 'fa6-solid:book-open-reader' },
  invoices_issued: { icon: 'fa6-solid:file-invoice', tone: 'positive' },
  invoice_cancellations: { icon: 'fa6-solid:file-circle-minus', tone: 'negative' },
  rebillings: { icon: 'fa6-solid:file-pen', tone: 'neutral' },
  recent_searches: { icon: 'fa6-solid:clock-rotate-left' },
  calendar: { icon: 'fa6-solid:calendar-days' },
  quick_access: { icon: 'fa6-solid:bars-progress' },
};

// Classes literals perquè Tailwind les inclogui al build.
export const DASHBOARD_SIZE_CLASSES = {
  sm: 'col-span-6 md:col-span-3 xl:col-span-2',
  md: 'col-span-6 xl:col-span-3',
  lg: 'col-span-6',
};

export const newCardId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

/** Configuració per defecte d'una card segons l'esquema del backend. */
export const defaultCardConfig = (card) => Object.fromEntries(
  (card?.config_schema || []).map(option => [option.name, option.default ?? null]),
);

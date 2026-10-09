export const RemoteTypeChoices = {
  'SMART_METERING': 'Smart Metering',
  'OTHER': `common.other`,
};

export const remoteTypeOptions = Object.entries(RemoteTypeChoices).map(([code, label]) => ({
  code,
  label,
}));
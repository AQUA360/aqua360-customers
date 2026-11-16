import { useI18n } from 'vue-i18n';

// Avís abans de treure un comptador d'un altre punt de subministrament.
// El servidor no el mou sense `confirm_reassign`: aquí es mostra on és ara
// (punt, adreça, contractes i titulars) i es demana confirmació expressa.
export function useMeterReassignConfirm() {
  const { t } = useI18n();
  const { $MeterApiService } = useNuxtApp();

  const formatAssignments = (assignments) => (assignments || []).map((a) => {
    const contracts = (a.contracts || []).length
      ? a.contracts.map((c) => (c.holder ? `${c.token} (${c.holder})` : c.token)).join(', ')
      : t('confirmation_text_block.meter_assignment_no_contracts');
    return t('confirmation_text_block.meter_assignment_line', {
      supply_point: a.supply_point_token || a.supply_point_id,
      address: a.address || '-',
      contracts,
    });
  }).join('\n');

  const confirmAssignments = (meterCode, assignments) => confirm(
    t('confirmation_text_block.confirm_reassign_meter', {
      code: meterCode || '',
      detail: formatAssignments(assignments),
    }),
  );

  // Retorna null si l'usuari cancel·la; si no, el valor de `confirm_reassign`
  // per enviar al servidor (true només si s'ha confirmat moure'l).
  const checkMeterReassign = async (meter, supplyPointId) => {
    if (!meter?.id || meter.is_general) return false;
    const response = await $MeterApiService.getAssignments(meter.id, supplyPointId);
    const assignments = response?.assignments || [];
    if (!assignments.length) return false;
    return confirmAssignments(meter.code, assignments) ? true : null;
  };

  return { checkMeterReassign, confirmAssignments };
}

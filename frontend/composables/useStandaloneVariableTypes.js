import { ref } from 'vue';

/**
 * Tipus de variable que es poden afegir soles a un contracte (o sol·licitud).
 *
 * Una variable que forma part d'un tipus de bonificació només s'ha d'afegir a través
 * d'aquella bonificació. Les úniques que es poden afegir individualment són les
 * personalitzades: les que no estan vinculades a cap tipus de bonificació.
 */
export function useStandaloneVariableTypes() {
  const standaloneVariableTypes = ref([]);
  const loadingStandaloneVariableTypes = ref(false);

  const getAllBonificationTypes = async ($BonificationTypeApiService) => {
    const all = [];
    let page = 1;
    let response;
    do {
      response = await $BonificationTypeApiService.getAll('', [], page);
      all.push(...response.results);
      page++;
    } while (response.next);
    return all;
  };

  const fetchStandaloneVariableTypes = async () => {
    const { $VariableTypeApiService, $BonificationTypeApiService } = useNuxtApp();
    loadingStandaloneVariableTypes.value = true;
    try {
      const [variableTypes, bonificationTypes] = await Promise.all([
        $VariableTypeApiService.getAllUnpaginated(),
        getAllBonificationTypes($BonificationTypeApiService),
      ]);

      // `variable_types` pot arribar com a ids o com a objectes sencers
      const linkedIds = new Set(
        bonificationTypes.flatMap(type => (type.variable_types || []).map(v => v?.id ?? v))
      );

      standaloneVariableTypes.value = variableTypes
        .filter(type => type.is_active && !linkedIds.has(type.id));
    } catch (err) {
      console.error(err);
      standaloneVariableTypes.value = [];
    } finally {
      loadingStandaloneVariableTypes.value = false;
    }
  };

  return { standaloneVariableTypes, loadingStandaloneVariableTypes, fetchStandaloneVariableTypes };
}

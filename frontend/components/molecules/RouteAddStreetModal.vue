<script setup>
// Afegir un carrer sencer a una ruta: es filtren els números del carrer (rang i paritat),
// es previsualitzen les posicions que es crearan i, en confirmar, el backend les insereix
// (desplaçant les posicions posteriors si cal).
import { ref, reactive, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const props = defineProps({
  routeId: {
    type: [Number, String],
    required: true
  }
});

const { t } = useI18n();
const toast = useToast();
const { $RouteApiService, $StreetApiService } = useNuxtApp();

const open = defineModel('open', { type: Boolean, default: false });
const emit = defineEmits(['done']);

const defaultForm = () => ({
  street: null,
  number_from: '',
  number_to: '',
  parity: 'all',
  order: 'asc',
  group_by: 'number',
  insert_at: '',
  assigned: 'skip'
});

const form = reactive(defaultForm());
const attempted = ref(false);
const preview = ref(null);
const loadingPreview = ref(false);
const loadingConfirm = ref(false);

const parityOptions = computed(() => [
  { value: 'all', label: t('service_block.route_add_street_parity_all') },
  { value: 'even', label: t('service_block.route_add_street_parity_even') },
  { value: 'odd', label: t('service_block.route_add_street_parity_odd') }
]);
const orderOptions = computed(() => [
  { value: 'asc', label: t('service_block.route_add_street_order_asc') },
  { value: 'desc', label: t('service_block.route_add_street_order_desc') }
]);
const groupByOptions = computed(() => [
  { value: 'number', label: t('service_block.route_add_street_group_number') },
  { value: 'property', label: t('service_block.route_add_street_group_property') }
]);
const assignedOptions = computed(() => [
  { value: 'skip', label: t('service_block.route_add_street_assigned_skip') },
  { value: 'move', label: t('service_block.route_add_street_assigned_move') }
]);

// AtomsInfiniteScrollVueSelect: (page, search) => { items: [{ value, label }], hasNextPage }
const loadStreets = async (page = 1, search = '') => {
  const data = await $StreetApiService.getAll(search || '', [], page);
  return {
    items: (data.results || []).map(street => ({
      value: street.id,
      label: [street.type?.abbreviation, street.name].filter(Boolean).join(' ')
        + (street.city?.name ? ` (${street.city.name})` : '')
    })),
    hasNextPage: !!data.next
  };
};

const toIntOrNull = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
};

const payload = computed(() => ({
  street_id: form.street?.value ?? null,
  number_from: toIntOrNull(form.number_from),
  number_to: toIntOrNull(form.number_to),
  parity: form.parity,
  order: form.order,
  group_by: form.group_by,
  insert_at: toIntOrNull(form.insert_at),
  assigned: form.assigned
}));

const rangeInvalid = computed(() => {
  const from = payload.value.number_from;
  const to = payload.value.number_to;
  return from !== null && to !== null && from > to;
});

const isValid = computed(() => !!payload.value.street_id && !rangeInvalid.value);

// Qualsevol canvi del formulari invalida la previsualització
watch(payload, () => {
  preview.value = null;
}, { deep: true });

const resetState = () => {
  Object.assign(form, defaultForm());
  attempted.value = false;
  preview.value = null;
  loadingPreview.value = false;
  loadingConfirm.value = false;
};

watch(open, (isOpen) => {
  if (!isOpen) resetState();
});

const busy = computed(() => loadingPreview.value || loadingConfirm.value);

const handleCancel = () => {
  if (busy.value) return;
  open.value = false;
};

const handlePreview = async () => {
  attempted.value = true;
  if (!isValid.value || loadingPreview.value) return;
  loadingPreview.value = true;
  try {
    preview.value = await $RouteApiService.addStreetPreview(props.routeId, payload.value);
  } catch (err) {
    console.error(err);
    preview.value = null;
  } finally {
    loadingPreview.value = false;
  }
};

const canConfirm = computed(() => (preview.value?.totals?.positions ?? 0) > 0);

const handleConfirm = async () => {
  if (!canConfirm.value || loadingConfirm.value) return;
  loadingConfirm.value = true;
  try {
    const result = await $RouteApiService.addStreet(props.routeId, payload.value);
    toast.success(t('service_block.route_add_street_success', {
      positions: result?.created_positions ?? 0,
      properties: result?.assigned_properties ?? 0
    }));
    open.value = false;
    emit('done', result);
  } catch (err) {
    console.error(err);
  } finally {
    loadingConfirm.value = false;
  }
};

const actionClass = (action) => {
  if (action === 'move') return 'bg-amber-100 text-amber-800';
  if (action === 'skip') return 'bg-slate-200 text-slate-600 line-through';
  return 'bg-sky-50 text-sky-800';
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleCancel" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="route-add-street-title" @click="handleCancel">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-4xl w-full relative max-h-[90vh] flex flex-col" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" :disabled="busy" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="route-add-street-title" class="text-lg font-semibold text-slate-800 mb-1 pr-8">
            {{ t('service_block.route_add_street') }}
          </h2>
          <p class="text-sm text-slate-600 mb-4">
            {{ t('service_block.route_add_street_help') }}
          </p>

          <div class="overflow-y-auto flex-1 min-h-0 pr-1">
            <!-- Formulari -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="sm:col-span-2">
                <AtomsInfiniteScrollVueSelect :labelText="t('address_block.street')" :loadFunction="loadStreets"
                  :item="form.street" @update:modelValue="form.street = $event" />
                <p v-if="attempted && !form.street" class="mt-1 text-xs text-red-600">
                  {{ t('service_block.route_add_street_street_required') }}
                </p>
              </div>

              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="block text-sm font-medium text-slate-500 mb-1" for="ras-number-from">
                    {{ t('service_block.route_add_street_number_from') }}
                  </label>
                  <input id="ras-number-from" v-model="form.number_from" type="number" min="0" step="1" class="input w-full"
                    :class="{ 'invalid': rangeInvalid }" :placeholder="t('common.optional')" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-500 mb-1" for="ras-number-to">
                    {{ t('service_block.route_add_street_number_to') }}
                  </label>
                  <input id="ras-number-to" v-model="form.number_to" type="number" min="0" step="1" class="input w-full"
                    :class="{ 'invalid': rangeInvalid }" :placeholder="t('common.optional')" />
                </div>
                <p v-if="rangeInvalid" class="col-span-2 text-xs text-red-600">
                  {{ t('service_block.route_add_street_range_invalid') }}
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-500 mb-1" for="ras-insert-at">
                  {{ t('service_block.route_add_street_insert_at') }}
                </label>
                <input id="ras-insert-at" v-model="form.insert_at" type="number" min="1" step="1" class="input w-full"
                  :placeholder="t('service_block.route_add_street_insert_at_placeholder')" />
              </div>

              <fieldset>
                <legend class="block text-sm font-medium text-slate-500 mb-1">{{ t('service_block.route_add_street_parity') }}</legend>
                <div class="flex flex-wrap gap-3">
                  <label v-for="opt in parityOptions" :key="opt.value" class="flex items-center gap-1 text-sm text-slate-700">
                    <input v-model="form.parity" type="radio" name="ras-parity" :value="opt.value" />
                    {{ opt.label }}
                  </label>
                </div>
              </fieldset>

              <fieldset>
                <legend class="block text-sm font-medium text-slate-500 mb-1">{{ t('service_block.route_add_street_order') }}</legend>
                <div class="flex flex-wrap gap-3">
                  <label v-for="opt in orderOptions" :key="opt.value" class="flex items-center gap-1 text-sm text-slate-700">
                    <input v-model="form.order" type="radio" name="ras-order" :value="opt.value" />
                    {{ opt.label }}
                  </label>
                </div>
              </fieldset>

              <fieldset>
                <legend class="block text-sm font-medium text-slate-500 mb-1">{{ t('service_block.route_add_street_group_by') }}</legend>
                <div class="flex flex-col gap-1">
                  <label v-for="opt in groupByOptions" :key="opt.value" class="flex items-center gap-1 text-sm text-slate-700">
                    <input v-model="form.group_by" type="radio" name="ras-group-by" :value="opt.value" />
                    {{ opt.label }}
                  </label>
                </div>
              </fieldset>

              <fieldset>
                <legend class="block text-sm font-medium text-slate-500 mb-1">{{ t('service_block.route_add_street_assigned') }}</legend>
                <div class="flex flex-col gap-1">
                  <label v-for="opt in assignedOptions" :key="opt.value" class="flex items-center gap-1 text-sm text-slate-700">
                    <input v-model="form.assigned" type="radio" name="ras-assigned" :value="opt.value" />
                    {{ opt.label }}
                  </label>
                </div>
              </fieldset>
            </div>

            <!-- Previsualització -->
            <div v-if="preview" class="mt-5 pt-4 border-t border-slate-100">
              <div class="flex flex-wrap gap-2 mb-3">
                <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                  {{ t('service_block.route_add_street_stat_positions', { count: preview.totals?.positions ?? 0 }) }}
                </span>
                <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                  {{ t('service_block.route_add_street_stat_properties', { count: preview.totals?.properties ?? 0 }) }}
                </span>
                <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                  {{ t('service_block.route_add_street_stat_supply_points', { count: preview.totals?.supply_points ?? 0 }) }}
                </span>
                <span v-if="preview.totals?.moved" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                  {{ t('service_block.route_add_street_stat_moved', { count: preview.totals.moved }) }}
                </span>
                <span v-if="preview.totals?.skipped" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-200 text-slate-600">
                  {{ t('service_block.route_add_street_stat_skipped', { count: preview.totals.skipped }) }}
                </span>
              </div>

              <p v-if="preview.insert_at" class="text-xs text-slate-600 mb-1">
                {{ t('service_block.route_add_street_insert_from', { position: preview.insert_at }) }}
              </p>
              <p v-if="preview.shift > 0" class="text-xs text-amber-700 mb-3 flex items-center gap-1">
                <Icon name="fa6-solid:triangle-exclamation" />
                {{ t('service_block.route_add_street_shift_warning', { count: preview.shift }) }}
              </p>
              <p v-if="!canConfirm" class="text-xs text-slate-600 mb-3">
                {{ t('service_block.route_add_street_nothing') }}
              </p>

              <div v-if="preview.positions?.length" class="border border-slate-200 rounded overflow-hidden">
                <table class="w-full text-sm">
                  <thead class="bg-slate-50 text-slate-600 text-left">
                    <tr>
                      <th class="px-3 py-2 font-medium w-20">{{ t('common.position') }}</th>
                      <th class="px-3 py-2 font-medium w-1/3">{{ t('address_block.street') }}</th>
                      <th class="px-3 py-2 font-medium">{{ t('common.properties') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="pos in preview.positions" :key="pos.position" class="border-t border-slate-100 align-top">
                      <td class="px-3 py-2 text-slate-500">{{ pos.position }}</td>
                      <td class="px-3 py-2 text-slate-800">{{ pos.label }}</td>
                      <td class="px-3 py-2">
                        <div class="flex flex-wrap gap-1">
                          <span v-for="prop in pos.properties" :key="prop.id"
                            class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs" :class="actionClass(prop.action)"
                            :title="prop.name || prop.token">
                            <span class="font-medium">{{ prop.token }}</span>
                            <span v-if="prop.supply_points_count" class="opacity-75">
                              · {{ t('service_block.route_add_street_sp_count', { count: prop.supply_points_count }) }}
                            </span>
                            <span v-if="prop.action === 'move' && prop.current_route" class="font-semibold no-underline">
                              · {{ t('service_block.route_add_street_badge_move', { route: prop.current_route.token }) }}
                            </span>
                            <span v-else-if="prop.action === 'skip'" class="font-semibold">
                              · {{ prop.current_route
                                ? t('service_block.route_add_street_badge_skip_route', { route: prop.current_route.token })
                                : t('service_block.route_add_street_badge_skip') }}
                            </span>
                          </span>
                          <span v-if="!pos.properties?.length" class="text-slate-400">—</span>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6 pt-4 border-t border-slate-100 flex-shrink-0">
            <button type="button" class="button-default" :disabled="busy" @click="handleCancel">
              {{ t('common.cancel') }}
            </button>
            <button type="button" class="button-default flex items-center gap-2" :disabled="busy"
              @click="handlePreview">
              <Icon :name="loadingPreview ? 'fa6-solid:spinner' : 'fa6-solid:eye'" :class="{ 'animate-spin': loadingPreview }" />
              {{ t('service_block.route_add_street_preview') }}
            </button>
            <button type="button" class="button-primary flex items-center gap-2"
              :disabled="!preview || !canConfirm || busy" @click="handleConfirm">
              <Icon :name="loadingConfirm ? 'fa6-solid:spinner' : 'fa6-solid:check'" :class="{ 'animate-spin': loadingConfirm }" />
              {{ loadingConfirm ? t('common.loading') + '...' : t('common.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

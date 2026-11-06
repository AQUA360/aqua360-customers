<script setup>
// Canvia la ruta d'un punt de subministrament independentment de la de la seva finca
// (ruta pròpia), o el torna a la ruta de la finca.
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const props = defineProps({
  supplyPointId: {
    type: Number,
    required: true
  },
  effectiveRoute: {
    type: Object,
    default: null
  }
});

const { t } = useI18n();
const toast = useToast();
const { $RouteApiService, $SupplyPointApiService } = useNuxtApp();

const open = defineModel('open', { type: Boolean, default: false });
const emit = defineEmits(['saved']);

const selectedRoute = ref(null); // { value, label }
const position = ref('');
const attempted = ref(false);
const saving = ref(false);
const resetting = ref(false);

const isOwnRoute = computed(() => !!props.effectiveRoute && props.effectiveRoute.inherited === false);
const busy = computed(() => saving.value || resetting.value);

const routeLabel = (route) => [route?.route_token, route?.route_name].filter(Boolean).join(' - ');

const initState = () => {
  attempted.value = false;
  saving.value = false;
  resetting.value = false;
  if (isOwnRoute.value) {
    selectedRoute.value = { value: props.effectiveRoute.route_id, label: routeLabel(props.effectiveRoute) };
    position.value = props.effectiveRoute.position ?? '';
  } else {
    selectedRoute.value = null;
    position.value = '';
  }
};

watch(open, (isOpen) => {
  if (isOpen) initState();
}, { immediate: true });

// AtomsInfiniteScrollVueSelect: (page, search) => { items: [{ value, label }], hasNextPage }
const loadRoutes = async (page = 1, search = '') => {
  const data = await $RouteApiService.getData(search || '', [], page);
  return {
    items: (data.results || []).map(route => ({
      value: route.id,
      label: [route.token, route.name].filter(Boolean).join(' - ')
    })),
    hasNextPage: !!data.next
  };
};

const toIntOrNull = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
};

const handleCancel = () => {
  if (busy.value) return;
  open.value = false;
};

const submit = async (data, loadingRef, successKey) => {
  loadingRef.value = true;
  try {
    const result = await $SupplyPointApiService.setRoute(props.supplyPointId, data);
    toast.success(t(successKey));
    emit('saved', result?.effective_route ?? null);
    open.value = false;
  } catch (err) {
    console.error(err);
  } finally {
    loadingRef.value = false;
  }
};

const handleSave = async () => {
  attempted.value = true;
  if (!selectedRoute.value?.value || busy.value) return;
  await submit(
    { route_id: selectedRoute.value.value, position: toIntOrNull(position.value) },
    saving,
    'service_block.supply_point_route_saved'
  );
};

const handleReset = async () => {
  if (busy.value) return;
  await submit({ route_id: null }, resetting, 'service_block.supply_point_route_reset_done');
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleCancel" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="supply-point-route-title" @click="handleCancel">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" :disabled="busy" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="supply-point-route-title" class="text-lg font-semibold text-slate-800 mb-1 pr-8">
            {{ t('service_block.supply_point_route_change') }}
          </h2>
          <p class="text-sm text-slate-600 mb-4">
            {{ t('service_block.supply_point_route_help') }}
          </p>

          <div v-if="effectiveRoute" class="mb-4 text-sm text-slate-600 flex flex-wrap items-center gap-2">
            <span>{{ t('service_block.supply_point_route_current') }}:</span>
            <span class="font-medium text-slate-800">{{ effectiveRoute.position_token || routeLabel(effectiveRoute) }}</span>
            <span class="px-2 py-0.5 rounded-full text-xs font-semibold"
              :class="isOwnRoute ? 'bg-violet-100 text-violet-800' : 'bg-slate-100 text-slate-600'">
              {{ isOwnRoute ? t('service_block.route_own_badge') : t('service_block.route_property_badge') }}
            </span>
          </div>

          <div class="space-y-3">
            <div>
              <AtomsInfiniteScrollVueSelect :labelText="t('route')" :loadFunction="loadRoutes"
                :item="selectedRoute" @update:modelValue="selectedRoute = $event" />
              <p v-if="attempted && !selectedRoute?.value" class="mt-1 text-xs text-red-600">
                {{ t('service_block.supply_point_route_required') }}
              </p>
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-500 mb-1" for="sp-route-position">
                {{ t('common.position') }}
              </label>
              <input id="sp-route-position" v-model="position" type="number" min="1" step="1" class="input w-full"
                :placeholder="t('service_block.route_add_street_insert_at_placeholder')" />
            </div>
          </div>

          <div class="flex flex-wrap justify-between gap-2 mt-6 pt-4 border-t border-slate-100">
            <button v-if="isOwnRoute" type="button" class="button-default flex items-center gap-2" :disabled="busy"
              @click="handleReset">
              <Icon :name="resetting ? 'fa6-solid:spinner' : 'fa6-solid:rotate-left'" :class="{ 'animate-spin': resetting }" />
              {{ t('service_block.supply_point_route_reset') }}
            </button>
            <span v-else />
            <div class="flex gap-2">
              <button type="button" class="button-default" :disabled="busy" @click="handleCancel">
                {{ t('common.cancel') }}
              </button>
              <button type="button" class="button-primary flex items-center gap-2" :disabled="busy" @click="handleSave">
                <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': saving }" />
                {{ t('common.save') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

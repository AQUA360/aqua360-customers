<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();
const { $ACABonificationApiService } = useNuxtApp();

const emit = defineEmits(['on-processed']);

const pending = ref(true);
const items = ref([]);
const selectedIds = ref(new Set());
const previewing = ref(false);
const generating = ref(false);

const showPreview = ref(false);
const previewData = ref(null);

const allSelected = computed(() => items.value.length > 0 && items.value.every(item => selectedIds.value.has(item.id)));

const getData = async () => {
  pending.value = true;
  try {
    const data = await $ACABonificationApiService.getPending();
    items.value = data.results || data;
    selectedIds.value = new Set(items.value.map(item => item.id));
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const toggleSelected = (id) => {
  const next = new Set(selectedIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  selectedIds.value = next;
}

const selectAll = () => {
  selectedIds.value = allSelected.value ? new Set() : new Set(items.value.map(item => item.id));
}

const updateAuthorizes = async (item, value) => {
  item.authorizes_census_review = value;
  try {
    await $ACABonificationApiService.update(item.id, { authorizes_census_review: value });
  } catch (err) {
    console.error(err);
  }
}

const updateField = async (item, field, value) => {
  item[field] = value;
  try {
    await $ACABonificationApiService.update(item.id, { [field]: value });
  } catch (err) {
    console.error(err);
  }
}

const acaResultOptions = [
  { value: '01', label: "01 - Acompleix requisits d'ampliació" },
  { value: '02', label: '02 - No és titular del contracte' },
  { value: '03', label: '03 - No disposa de comptador individual' },
  { value: '04', label: '04 - No són usos domèstics' },
  { value: '05', label: '05 - El titular no és persona física' },
  { value: '06', label: "06 - Nombre d'habitants inferior a 4" },
  { value: '07', label: "07 - Ja disposa de la condició d'ampliació" },
  { value: '08', label: '08 - La companyia no subministra en aquesta adreça' },
  { value: '20', label: '20 - Tancament: no titular del contracte' },
  { value: '21', label: '21 - Tancament: 3 o menys persones' },
  { value: '22', label: '22 - Tancament: baixa padró o canvi adreça' },
];

const censatAdrecaOptions = [
  { value: '1', label: "Censat en l'adreça" },
  { value: '2', label: "No censat en l'adreça" },
  { value: '3', label: 'No validat' },
];

// Valors per defecte mostrats al formulari mentre el registre encara no en té
// un de desat: només visuals, no es persisteixen fins que l'usuari interactuï.
const getAuthorizesDefault = (item) => item.authorizes_census_review ?? true;
const getAcaResultDefault = (item) => item.aca_result ?? acaResultOptions[0].value;
const getCensatAdrecaDefault = (item) => item.censat_adreca ?? censatAdrecaOptions[0].value;
const getNumPersonsCensatsDefault = (item) => item.num_persons_censats ?? item.num_persons_to_apply ?? null;

const openPreview = async () => {
  if (selectedIds.value.size === 0) return;
  previewing.value = true;
  try {
    previewData.value = await $ACABonificationApiService.previewExport(Array.from(selectedIds.value));
    showPreview.value = true;
  } catch (err) {
    toast.error(err.message || t('common.error'));
  } finally {
    previewing.value = false;
  }
}

const closePreview = () => {
  if (generating.value) return;
  showPreview.value = false;
  previewData.value = null;
}

const confirmGenerateExport = async () => {
  generating.value = true;
  try {
    await $ACABonificationApiService.generateExport(Array.from(selectedIds.value));
    toast.success(t('common.success'));
    showPreview.value = false;
    previewData.value = null;
    emit('on-processed');
    await getData();
  } catch (err) {
    toast.error(err.message || t('common.error'));
  } finally {
    generating.value = false;
  }
}

onMounted(getData);
</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('common.aca_bonifications_pending') }}</H1>
      <button v-if="!pending && items.length > 0" class="button-default" @click="selectAll">
        <Icon name="fa6-solid:check-all" />
        {{ allSelected ? $t('common.deselect_all') : $t('common.select_all') }}
      </button>
    </div>

    <div v-if="pending" class="h-full min-h-[200px]">
      <AppLoading :text="$t('common.loading')" />
    </div>

    <div v-else-if="items.length === 0" class="my-3">
      <p>{{ $t('common.no_pending_aca_bonifications') }}</p>
    </div>

    <div v-else class="overflow-x-auto">
      <div class="min-w-[900px] heading grid grid-cols-[20px,1fr,1fr,90px,90px,220px,150px,90px] gap-3 border-b text-base items-center pb-2">
        <span>&nbsp;</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.contract') }}</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.holder') }}</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.num_persons_to_apply') }}</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.authorizes_census_review') }}</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.aca_result') }}</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.censat_adreca') }}</span>
        <span class="p-1 font-semibold text-slate-700">{{ $t('common.num_persons_censats') }}</span>
      </div>

      <div v-for="item in items" :key="item.id"
        class="min-w-[900px] grid grid-cols-[20px,1fr,1fr,90px,90px,220px,150px,90px] gap-3 border-b text-base items-center bg-white"
        :class="{ 'bg-yellow-50': selectedIds.has(item.id) }">
        <input type="checkbox" :checked="selectedIds.has(item.id)" @change="toggleSelected(item.id)" />
        <span class="p-1 text-nowrap">{{ item.contract_token }}</span>
        <span class="p-1 truncate">{{ item.holder_name }}</span>
        <span class="p-1 text-center">{{ item.num_persons_to_apply ?? '-' }}</span>
        <input type="checkbox" :checked="getAuthorizesDefault(item)"
          @change="updateAuthorizes(item, $event.target.checked)" />
        <select class="w-full p-1 rounded border border-gray-300 text-xs" :value="getAcaResultDefault(item)"
          @change="updateField(item, 'aca_result', $event.target.value || null)">
          <option value="">--</option>
          <option v-for="opt in acaResultOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select class="w-full p-1 rounded border border-gray-300 text-xs" :value="getCensatAdrecaDefault(item)"
          @change="updateField(item, 'censat_adreca', $event.target.value || null)">
          <option value="">--</option>
          <option v-for="opt in censatAdrecaOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <input type="number" min="0" max="20" class="w-full p-1 rounded border border-gray-300" :value="getNumPersonsCensatsDefault(item)"
          @change="updateField(item, 'num_persons_censats', $event.target.value ? parseInt($event.target.value) : null)" />
      </div>

      <div class="col-span-3 flex flex-row-reverse mt-4">
        <button class="button-primary" :disabled="previewing || selectedIds.size === 0" @click="openPreview">
          <Icon name="fa6-solid:eye" />&nbsp; {{ $t('common.preview_export_file') }}
        </button>
      </div>
    </div>

    <!-- Modal de previsualització i confirmació -->
    <div v-if="showPreview">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-40 flex items-center justify-center" @click="closePreview"></div>

      <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-3xl w-full mx-4 my-auto relative pointer-events-auto">
          <button @click="closePreview" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700" :disabled="generating">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h3 class="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Icon name="fa6-solid:file-lines" class="text-slate-500" />
            {{ $t('common.preview_export_file') }}
          </h3>

          <p class="text-sm text-slate-600 mb-2">{{ previewData?.file_name }}</p>

          <pre class="whitespace-pre overflow-x-auto text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3 max-h-80 overflow-y-auto">{{ previewData?.content }}</pre>

          <div class="mt-4 rounded-lg px-3 py-2 text-sm font-semibold flex items-start gap-2 bg-yellow-50 text-yellow-800 border border-yellow-200">
            <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5" />
            {{ $t('common.aca_generate_warning') }}
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <button @click="closePreview" :disabled="generating"
              class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50">
              {{ $t('common.cancel') }}
            </button>
            <button @click="confirmGenerateExport" :disabled="generating" class="button-primary">
              <Icon name="fa6-solid:file-export" />&nbsp; {{ $t('common.generate_export_file') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

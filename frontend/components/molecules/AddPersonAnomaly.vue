<script setup>
// Alta d'una anomalia de la persona (subregió de la fitxa de la persona)
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';

const props = defineProps({
  personId: { type: Number, required: true },
});

const emit = defineEmits(['change', 'close']);

const { t, te } = useI18n();
const toast = useToast();
const { $PersonAnomalyApiService } = useNuxtApp();

const localToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

const types = ref([]);
const loadingTypes = ref(false);
const anomalyType = ref(null);
const startDate = ref(localToday());
const endDate = ref(null);
const observation = ref('');
const attemptedSave = ref(false);
const loading = ref(false);

const typeOptions = computed(() => types.value.map((type) => {
  const key = `person_anomaly.types.${type.token}`;
  return { value: type.id, label: te(key) ? t(key) : type.name };
}));

const invalidEndDate = computed(() => !!endDate.value && !!startDate.value && endDate.value < startDate.value);
const canSave = computed(() => !!anomalyType.value && !!startDate.value && !invalidEndDate.value && !loading.value);

const getTypes = async () => {
  loadingTypes.value = true;
  try {
    const res = await $PersonAnomalyApiService.getTypes();
    types.value = res.results || res || [];
  } catch (err) {
    console.error(err);
  } finally {
    loadingTypes.value = false;
  }
};

const save = async () => {
  attemptedSave.value = true;
  if (!canSave.value) return;
  loading.value = true;
  try {
    await $PersonAnomalyApiService.save({
      person: props.personId,
      anomaly_type_id: anomalyType.value.value,
      start_date: startDate.value,
      end_date: endDate.value || null,
      observation: observation.value?.trim() || null,
    });
    toast.success(t('common.correct_save'));
    emit('change');
  } catch (err) {
    console.error(err);
  } finally {
    loading.value = false;
  }
};

onMounted(getTypes);
</script>

<template>
  <div class="region__content px-4 pb-4 pt-2 md:px-6 md:pb-6">
    <div class="mb-4 flex items-center justify-between gap-2">
      <H1Region>{{ t('person_anomaly.add') }}</H1Region>
    </div>

    <section class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <div class="grid md:grid-cols-2 gap-2">
        <div class="md:col-span-2">
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            {{ t('person_anomaly.anomaly_type') }}
          </label>
          <v-select class="block w-full custom-select" v-model="anomalyType" :options="typeOptions"
            :loading="loadingTypes" :class="{ 'invalid': attemptedSave && !anomalyType }" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
            for="anomaly_start_date">
            {{ t('person_anomaly.start_date') }}
          </label>
          <input id="anomaly_start_date" v-model="startDate" type="date" class="input w-full text-sm"
            :class="{ 'border-red-400 focus:border-red-500': attemptedSave && !startDate }" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
            for="anomaly_end_date">
            {{ t('person_anomaly.end_date') }}
          </label>
          <input id="anomaly_end_date" v-model="endDate" type="date" :min="startDate" class="input w-full text-sm"
            :class="{ 'border-red-400 focus:border-red-500': invalidEndDate }" />
        </div>

        <div class="md:col-span-2">
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
            for="anomaly_observation">
            {{ t('person_anomaly.observation') }}
          </label>
          <textarea id="anomaly_observation" v-model="observation" rows="3" class="input w-full text-sm"></textarea>
        </div>
      </div>
    </section>

    <div class="mt-4 flex justify-end">
      <button class="button-primary flex items-center gap-2" :disabled="!canSave" @click="save">
        <Icon :name="loading ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': loading }" />
        {{ t('common.save') }}
      </button>
    </div>
  </div>
</template>

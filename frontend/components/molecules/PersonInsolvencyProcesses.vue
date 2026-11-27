<script setup>
// Processos d'insolvència d'una persona (pestanya de la fitxa de la persona)
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import InsolvencyProcessRegion from '~/components/organisms/InsolvencyProcessRegion.vue';

const props = defineProps({
  personId: { type: Number, required: true },
});

const emit = defineEmits(['change']);

const { t } = useI18n();
const { $InsolvencyProcessApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const processes = ref([]);
const permissions = ref(null);

const getData = async () => {
  const personId = props.personId;
  pending.value = true;
  error.value = null;
  try {
    if (!permissions.value) permissions.value = await $InsolvencyProcessApiService.getPermissions();
    if (!permissions.value?.can_view) {
      processes.value = [];
      return;
    }
    const res = await $InsolvencyProcessApiService.getAll(1, { person_id: personId });
    if (personId === props.personId) processes.value = res.results || [];
  } catch (err) {
    if (personId === props.personId) error.value = err;
  } finally {
    if (personId === props.personId) pending.value = false;
  }
};

const onChange = async () => {
  await getData();
  emit('change');
};

onMounted(getData);
watch(() => props.personId, getData);
</script>

<template>
  <div class="px-4">
    <div v-if="pending" class="footering text-slate-500 p-2">{{ t('common.loading') }}...</div>
    <div v-else-if="error" class="footering text-red-600 p-2">{{ t('common.error_load') }}</div>
    <div v-else-if="!permissions?.can_view" class="footering text-slate-500 p-2">{{ t('common.no_permissions') }}</div>
    <div v-else-if="!processes.length" class="footering text-slate-500 p-2">{{ t('common.no_records') }}</div>
    <div v-else class="space-y-4">
      <div v-for="process in processes" :key="process.id"
        class="rounded-xl border px-4 py-3 shadow-sm" :class="process.status === 'open' ? 'border-red-200' : 'border-slate-200'">
        <InsolvencyProcessRegion :id="process.id" :permissions="permissions" :embedded="true" @change="onChange" />
      </div>
    </div>
  </div>
</template>

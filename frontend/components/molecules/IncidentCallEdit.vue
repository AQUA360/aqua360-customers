<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';
import AddNewCall from './AddNewCall.vue';

// Registre d'una trucada vinculada a la incidència, a un dels contactes del contracte
const props = defineProps({
  incident: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['changed']);
const { $ContractApiService } = useNuxtApp();
const { t } = useI18n();

const loading = ref(true);
const loadError = ref(false);
const contract = ref(null);
const newCall = ref(null);

const contacts = computed(() => (contract.value?.contacts || []).filter(contact => contact.phone && contact.is_active !== false));

const getData = async () => {
  loading.value = true;
  loadError.value = false;
  try {
    contract.value = props.incident.contract ? await $ContractApiService.getDetail(props.incident.contract.id) : null;
  } catch (err) {
    console.error('Error obtenint el contracte:', err);
    loadError.value = true;
  } finally {
    loading.value = false;
  }
};

const startCall = (contact) => {
  newCall.value = {
    contact: contact,
    contract: contract.value,
    incident: props.incident,
  };
};

const handleExit = () => {
  newCall.value = null;
  emit('changed');
};

onMounted(getData);
</script>

<template>
  <div>
    <div v-if="loading" class="flex justify-center items-center h-48">
      <span class="text-lg text-gray-600">{{ $t('common.loading') }}...</span>
    </div>

    <div v-else-if="loadError" class="text-sm text-red-600">
      {{ t('common.error_loading_data') }}
      <button class="text-sky-500 underline ml-2" @click="getData">{{ t('common.retry') }}</button>
    </div>

    <AddNewCall v-else-if="newCall" :data="newCall" @exit="handleExit" />

    <div v-else>
      <H1Region class="mb-4">{{ t('incident_block.new_call') }}</H1Region>
      <div v-if="contacts.length === 0" class="text-sm text-slate-500">
        {{ t('incident_block.no_contacts') }}
      </div>
      <div v-else>
        <p class="text-sm text-slate-500 mb-2">{{ t('incident_block.select_contact') }}</p>
        <div class="space-y-1">
          <button v-for="contact in contacts" :key="contact.id" @click="startCall(contact)"
            class="w-full grid grid-cols-[20px,1fr,auto] gap-2 items-center text-left border border-slate-200 px-3 py-2 rounded hover:bg-slate-50">
            <Icon name="fa6-solid:phone" class="text-xs text-slate-400" />
            <span>
              <span class="font-semibold">{{ contact.person_full_name }}</span>
              <span class="text-sky-500 ml-2">{{ contact.phone }}</span>
            </span>
            <span v-if="contact.role" class="text-sm text-slate-500">({{ contact.role }})</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

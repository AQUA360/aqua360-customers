<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatDate } from '~/utils/date';

const props = defineProps({
  request: Object
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close']);
const { $ClaimRequestApiService } = useNuxtApp();

const loading = ref(false);
const terminations = ref([]);

// Carregar les baixes associades a la reclamació
const loadTerminations = async () => {
  loading.value = true;
  try {
    // Aquí hauríem d'afegir la crida a l'API quan estigui disponible
    terminations.value = props.request.contract_termination_requests || [];
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// Carregar les baixes al iniciar
onMounted(async () => {
  await loadTerminations();
});
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold">{{ $t('common.contract_terminations') }}</h3>
      <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700">
        <Icon name="fa6-solid:xmark" class="text-xl" />
      </button>
    </div>

    <div class="flex-1 overflow-y-auto">
      <div v-if="loading" class="flex justify-center items-center h-full">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
      </div>
      <div v-else>
        <div v-if="terminations.length === 0" class="text-gray-500 text-center py-4">
          {{ $t('common.no_data_found') }}
        </div>
        <div v-else class="ml-4 mt-4">
          <div class="grid grid-cols-7 gap-3 border-b text-slate-500 py-1">
            <div>{{ $t('common.identification') }}</div>
            <div>{{ $t('contract') }}</div>
            <div class="col-span-2">{{ $t('contract_block.holder') }}</div>
            <div>{{ $t('common.type') }}</div>
            <div>{{ $t('common.status') }}</div>
            <div>{{ $t('common.date') }}</div>
          </div>
          <div v-for="termination in terminations" :key="termination.id" class="grid grid-cols-7 gap-3 py-1">
            <div>{{ termination.token }}</div>
            <div>{{ termination.contract?.token || '-' }}</div>
            <div>{{ termination.contract?.holder || '-' }}</div>
            <div>{{ termination.contract?.holder_token || '-' }}</div>
            <div>{{ termination.type?.name || '-' }}</div>
            <div>
              <AtomsColorBadge :value="termination.status?.name || termination.status?.token" :color="termination.status?.color" />
            </div>
            <div>{{ formatDate(termination.created_at) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template> 
<script setup>
import { ref } from 'vue';
import H1Region from '~/components/atoms/H1Region.vue';
import ContractDocumentsData from '~/components/molecules/ContractDocumentsData.vue';

const { t } = useI18n();

const props = defineProps({
  request: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['close', 'change']);

const handleUpdateItem = (updatedRequest) => {
  emit('change', updatedRequest);
};

const handleRefresh = () => {
  emit('change', props.request);
};
</script>

<template>
  <div class="region__content h-full pr-2 overflow-y-auto">
    <div class="flex justify-between relative mb-6">
      <div class="flex items-center gap-5">
        <H1Region>{{ $t('common.documentation') }}</H1Region>
      </div>
      <div>
        <!-- Additional actions can be placed here if needed -->
      </div>
    </div>
    <div v-if="request" class="text-base">
        <div class="mb-4">
            <p class="text-slate-600 mb-2">
                {{ $t('contract_block.add_documentation_info') }}
            </p>
        </div>
      <ContractDocumentsData 
        :contract="request" 
        :is_request="true"
        @update-item="handleUpdateItem"
        @refresh="handleRefresh" 
      />
    </div>
    <div v-else>
      <p class="text-slate-500">{{ $t('common.no_data_found') }}</p>
    </div>
  </div>
</template>

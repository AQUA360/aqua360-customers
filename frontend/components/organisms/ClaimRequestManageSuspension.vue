<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';

const props = defineProps({
  request: Object,
  step: Object,
  isFirstStep: {
    type: Boolean,
    default: false
  },
  isLastStep: {
    type: Boolean,
    default: false
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['changed', 'previous-step', 'next-step', 'show-letter']);
const { $ClaimRequestApiService } = useNuxtApp();

const downloading = ref(false);
const saving = ref(false);
const letterDate = ref(props.step.action_date_at);

const closeWarning = ref(props.request.vulnerable_pending_requests_count === 0 && props.request.vulnerable_accepted_requests_not_exclosed_count === 0)
const atCurrentStep = computed(() => {
  return props.request.current_step?.id === props.step.id;
});

const handleDownloadLetter = async () => {
  downloading.value = true;
  try {
    let save_data = {
      id: props.request.id,
      step_id: props.step.id
    }
    let response = await $ClaimRequestApiService.downloadClaimDocument(save_data);
    if (response) {
      const blob = new Blob([response], { type: 'application/pdf' });

      const url = window.URL.createObjectURL(blob);

      const date = new Date();
      const today = date.getFullYear().toString() +
        String(date.getMonth() + 1).padStart(2, '0') +
        String(date.getDate()).padStart(2, '0');
      const a = document.createElement('a');
      a.href = url;
      a.download = `${props.step.document_type.token}${today}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      window.URL.revokeObjectURL(url);

      toast.success(t('common.correct_download'));
    }
  } catch (error) {
    toast.error(t('common.error_download'));
    console.error(error);
  } finally {
    downloading.value = false;
  }
};

const newCommunicationProcess = () => {
  return navigateTo('/communication/process-communications/add?claim_request_id=' + props.request.id)
}

</script>

<template>
  <div class="space-y-4">
    <div v-if="!closeWarning && request?.vulnerable_pending_requests_count && request.vulnerable_pending_requests_count > 0" class="my-2 border border-yellow-500 rounded-lg p-4 bg-yellow-100">
      <div class="grid grid-cols-[auto,1fr,auto] gap-2 flex items-center">
        <Icon name="fa6-solid:triangle-exclamation" class="text-yellow-600" />
        <div>
          <p class="text-yellow-600 font-semibold">{{ $t('contract_block.vulnerable_mng_pending') }}</p>
          <p class="text-yellow-600 font-semibold">{{
            $t('common.pending_requests') }}: {{ request?.vulnerable_pending_requests_count }}</p>
          <p v-if="request.vulnerable_accepted_requests_not_exclosed_count > 0" class="text-yellow-600 font-semibold">{{
            $t('common.accepted_requests') }}: {{ request.vulnerable_accepted_requests_not_exclosed_count }}
          </p>
        </div>
        <button @click="closeWarning = true" class="font-bold hover:underline flex items-center">
          <Icon name="fa6-solid:xmark" class="text-yellow-600 hover:text-yellow-800 text-lg" />
        </button>
      </div>
    </div>
    <div class="flex justify-between">
      <div>
        <h3 class="text-lg font-semibold">{{ $t('common.send') }} {{ $t('claim_block.suspension_letter') }}</h3>
        <p class="text-gray-600">{{ $t('informative_block.info_suspension_letter') }}</p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <abbr class="italic" :title="`${$t('common.add')} ${$t('common.send_date')}`">
          {{ $t('common.start_date') }}:
          {{ step?.action_date_at ? formatDate(step.action_date_at) : '-' }}
        </abbr>
        <abbr class="italic"
          :title="step?.step_template.duration + ' ' + step?.step_template.duration_type + ' ' + $t('date.days')">
          {{ $t('common.end_date') }}:
          {{ step?.due_date ? formatDate(step.due_date) : '-' }}
        </abbr>
        <abbr class="italic">
          {{ $t('common.completion_date') }}:
          {{ step?.end_step_date ? formatDate(step.end_step_date) : '-' }}
        </abbr>
      </div>
    </div>


    <div v-if="!step.communication_process">
      <button class="button-primary flex items-center gap-2" @click="newCommunicationProcess" :disabled="!atCurrentStep">
        <Icon name="fa6-solid:envelopes-bulk" />
        {{ t('common.generate') }} {{ $t('common.comms_process_detail') }}
      </button>
    </div>

    <div v-else>
      <div class="flex items-center justify-between">
        <button class="button-default flex items-center gap-2"
          @click="emit('show-letter', step.communication_process.id)">
          <Icon name="fa6-solid:eye" />
          <Icon name="fa6-solid:envelopes-bulk" />
          {{ t('common.show') }} {{ $t('common.comms_process_detail') }}
        </button>

        <button class="button-secondary flex items-center gap-2" @click="handleDownloadLetter" :disabled="downloading">
          <Icon :name="downloading ? 'fa6-solid:spinner' : 'fa6-solid:envelopes-bulk'"
            :class="{ 'animate-spin': downloading }" />
          {{ t('common.download') }} {{ $t('customer_service_block.letters') }}
        </button>
      </div>

      <div class="px-4 py-2 border border-slate-300 w-[350px] rounded mt-3">
        <div class="flex items-center justify-between gap-2 text-slate-400">
          {{ t('common.comms') }}:
          <span class="font-semibold text-slate-500">
            {{ step.communication_process.total_communications }}
          </span>
        </div>

        <div class="flex items-center justify-between gap-2 text-slate-400">
          {{ t('customer_service_block.sent_comms') }}:
          <span class="font-semibold text-sky-500">
            {{ step.communication_process.total_sent_communications }}
          </span>
        </div>

        <div class="flex items-center justify-between gap-2 text-slate-400">
          <p>
            {{ t('common.description') }}:
          </p>
          <abbr :title="step.communication_process.description" class="font-semibold text-slate-500 truncate">
            {{ step.communication_process.description }}
          </abbr>
        </div>
      </div>
    </div>

    <!-- <div>
      <button class="button-secondary flex items-center gap-2" @click="handleDownloadLetter" :disabled="downloading">
        <Icon :name="downloading ? 'fa6-solid:spinner' : 'fa6-solid:envelopes-bulk'"
          :class="{ 'animate-spin': downloading }" />
        TEST descàrrega carta suspensió
      </button>
    </div> -->

    <div v-if="!atCurrentStep" class="text-sm text-amber-500 text-bold">
        {{ $t('claim_block.info_at_current_step') }}
      </div>

    <slot name="footer" />

  </div>
</template>
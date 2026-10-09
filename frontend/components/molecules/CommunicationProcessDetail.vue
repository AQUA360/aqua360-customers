<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $CommunicationProcessApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  },
  updatingMessagesTaskId: {
    type: Number,
    required: false
  }
});

const emit = defineEmits(['show-detail', 'edit', 'refresh']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);
const processing_status_token = ref(null)
const updatingMessagesTaskId = ref(null)

const fetchData = async (loading = true) => {
  isLoading.value = loading;
  try {
    const detail = await $CommunicationProcessApiService.getDetail(props.id);
    localData.value = detail;
    updatingMessagesTaskId.value = detail.updating_messages_task_id;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

const refreshData = async () => {
  await fetchData(false);
  emit('refresh');
}

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}


onMounted(async () => {
  if (!props.data && props.id) {
    fetchData();
  }
  processing_status_token.value = await $ConfigProjectApiService.get('communication_process_status_processing_token');

});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});

watch(() => props.updatingMessagesTaskId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    updatingMessagesTaskId.value = newId;
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
    }}</span>
  </div>

  <div v-else-if="localData">
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.identification")' :value=localData.token />
      <FieldDetail :label="$t('common.status')">
        <AtomsProcessColorBadge class="w-fit" v-if="localData.status.token == processing_status_token" @refresh="refreshData"
        :value="localData.status?.name" :color="localData.status?.color" :taskId="localData.task_id"></AtomsProcessColorBadge>
        <AtomsColorBadge v-else :value=localData.status.name :color=localData.status.color />
      </FieldDetail>
      <FieldDetail v-if="localData.billing" :label='$t("billing")'>
        <div v-if="!isSubRegion" class="flex gap-2">
            <button @click="showDetail('BillingRegion', localData.billing?.id)"
              class="text-start text-sky-500 underline flex items-center gap-2">
              {{ localData.billing?.token }}
            </button>
            <AtomsRedirectButton :id="localData.billing.id" :path="'/billing/billing/'" />
          </div>
          <span v-else>
            {{ localData.billing?.token }}
          </span>
      </FieldDetail>
      <FieldDetail v-if="localData.claim_request" :label="t('claim_block.claim_payments')">
        <div v-if="!isSubRegion" class="flex gap-2">
            <!-- <button @click="showDetail('ClaimRequestRegion', localData.claim_request?.id)"
              class="text-start text-sky-500 underline flex items-center gap-2">
              {{ localData.claim_request?.token }}
            </button> -->
            <AtomsRedirectButton :id="localData.claim_request.id" :path="'/billing/claim-managements/'" class="group hover:text-sky-600" >
              <template #text>
                <span class="text-sky-500 underline flex items-center gap-2 group-hover:no-underline group-hover:text-sky-600">
                  {{ localData.claim_request?.token }}
                </span>
              </template>
            </AtomsRedirectButton>
          </div>
          <span v-else>
            {{ localData.claim_request?.token }}
          </span>
      </FieldDetail>
      <AtomsProcessColorBadge class="w-[50%] py-2" v-if="updatingMessagesTaskId" @refresh="refreshData"
        :value="`${t('common.generating')} ${t('messages').toLowerCase()}`" :color="'blue'" :taskId="updatingMessagesTaskId"></AtomsProcessColorBadge>
      <FieldDetail :label='$t("common.use_type")' :value=localData.use_type?.name />

      <hr class="my-2 col-span-2">

      <FieldDetail class="col-span-2 truncate" :label='$t("common.description")' :value=localData.description />
      <FieldDetail v-if="localData.type_names" class="col-span-2 truncate" :label='$t("common.type")' :value=localData.type_names />
      <FieldDetail class="" :label='$t("common.send_date")' :value="localData.due_date ? formatDate(localData.due_date) : '-' " />
      <FieldDetail class="" :label='$t("user")' :value="localData.user.username" />
    </div>
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>

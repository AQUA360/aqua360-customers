<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $CommunicationApiService } = useNuxtApp();
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
  }
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $CommunicationApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}


onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});

watch(() => props.data, (newData) => {
  if (newData) {
    localData.value = { ...newData };
  }
}, { deep: true });
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
        <AtomsColorBadge :value=localData.status.name :color=localData.status.color />
      </FieldDetail>
      <FieldDetail :label='$t("customer_service_block.recipient")'>
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('PersonRegion', localData.person.id)"
            class="text-start text-sky-500 underline">{{ localData.person.full_name }}</button>
          <AtomsRedirectButton :id="localData.person.id" :path="'/contract/persons/'" />
        </div>
        <span v-else>{{ localData.person.full_name }}</span>
      </FieldDetail>
      <FieldDetail :label='$t("company")'>
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('CompanyRegion', localData.config_company.id)"
            class="text-start text-sky-500 underline">{{ localData.config_company.alias }}</button>
          <AtomsRedirectButton :id="localData.config_company.id" :path="'/company/companies/'" />
        </div>
        <span v-else>{{ localData.config_company.alias }}</span>
      </FieldDetail>
      <FieldDetail v-if="localData.process" :label='$t("customer_service_block.process")'>
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('CommunicationProcessRegion', localData.process.id)"
            class="text-start text-sky-500 underline">{{ localData.process.token }}</button>
          <AtomsRedirectButton :id="localData.process.id" :path="'/communication/process-communications/'" />
        </div>
        <span v-else>{{ localData.process.token }}</span>
      </FieldDetail>
      <FieldDetail :label='$t("common.use_type")' :value="localData.use_type?.name || '-'" />
      <FieldDetail :label='$t("service_block.config_mail_sender")' :value="localData.company_config_email?.mail_send_mail || '-'" />
      <FieldDetail class="col-span-2" :label='$t("customer_service_block.channel")' :value=localData.type_names />
      <div class="flex items-center ml-2 text-slate-500">
        <input v-model="localData.always_attach" type="checkbox" id="always_attach" name="always_attach" class="checkbox"
          :disabled="true" />
        <label for="always_attach" class="ml-2"> {{ t('customer_service_block.always_attach') }}</label>
      </div>
    </div>

    <hr class="my-2" />
    
    <div role="row" class="grid grid-cols-2">
      <FieldDetail class="truncate" :label='$t("common.email_long")' :value="localData.used_email? localData.used_email : t('common.no_email') " />
      <!-- <FieldDetail class="truncate" :label='$t("customer_service_block.short_tlf_sms")' :value="localData.used_phones? localData.used_phones : t('common.no_tlf') " /> -->
      <FieldDetail class="col-span-2" :label='$t("address_block.address")' :value="localData.used_address? localData.used_address : t('address_block.no_address') " />
      <FieldDetail v-if="localData.accounting_office" :label='$t("billing_block.short_accounting_office")' :value="localData.accounting_office" />
      <FieldDetail v-if="localData.managing_body && localData.managing_body != localData.accounting_office && localData.managing_body != localData.processing_unit"
       :label='$t("billing_block.short_managing_body")' :value="localData.managing_body" />
      <FieldDetail v-if="localData.processing_unit && localData.processing_unit != localData.accounting_office && localData.processing_unit != localData.managing_body" 
      :label='$t("billing_block.short_processing_unit")' :value="localData.processing_unit" />
      <hr class="my-2 col-span-2" />
      <FieldDetail class="" :label="$t('common.send_date')" :value="localData.due_date ? formatDate(localData.due_date) : '-' " />
      <FieldDetail class="" :label='$t("customer_service_block.sent")' :value="localData.sent_at ? formatDate(localData.sent_at) : '-' " />
      <FieldDetail class="" :label='$t("user")' :value=localData.user.username />
    </div>
    <FieldDetail v-if="localData.rejection_reason" class="col-span-2" :label="$t('customer_service_block.rejection_reason')">
      <span class="inline-block rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-900">{{ localData.rejection_reason }}</span>
    </FieldDetail>
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>

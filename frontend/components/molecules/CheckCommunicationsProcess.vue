<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '../atoms/H1Region.vue';
import CheckCommunicationsProcessData from './CheckCommunicationsProcessData.vue';

const toast = useToast();
const { t } = useI18n()

const props = defineProps({
  communicationIds: {
    type: Array,
    default: () => [],
  },
});

const { $ConfiglistApiService, $CommunicationProcessApiService } = useNuxtApp();
const activeTab = ref('communications');
const setActiveTab = (tab) => {
  activeTab.value = tab;
};

const loadingCompaniesConfig = ref(false);
const companiesConfig = ref([]);
const selectedCompanyConfig = ref(null);
const communicationUseTypes = ref([]);
const selectedCommunicationUseType = ref(null);
const dueDate = ref(null);
const description = ref('');

const excludedCommunicationIds = ref([]);
const saving = ref(false);

const allowSave = computed(() => {
  return selectedCompanyConfig.value && dueDate.value && selectedCommunicationUseType.value && description.value && props.communicationIds.length > 0 && excludedCommunicationIds.value.length < props.communicationIds.length;
});

const missingConfig = computed(() => {
  return (!selectedCompanyConfig.value || !dueDate.value || !selectedCommunicationUseType.value || !description.value) && activeTab.value !== 'config';
});

const fetchConfigData = async (service, entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];
    if (data.results) {
      data.results.forEach(item => {
        targetArray.value.push({
          label: item.name ? item.name : item.token,
          value: item.id,
          token: item.token,
          is_default: item.is_default || false,
        });
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
};

const getCompaniesConfig = async () => {
  loadingCompaniesConfig.value = true;
  try {
    const result = await $ConfiglistApiService.getAll('service/company-config');
    companiesConfig.value = [];
    result.results.forEach(company => {
      companiesConfig.value.push({
        label: company.name,
        code: company.id,
        company: company.company,
      });
    });
  } catch (err) {
    console.error(err);
  } finally {
    loadingCompaniesConfig.value = false;
  }
};

const save = async () => {
  saving.value = true;

  try {
    const payload = {
      comm_ids: props.communicationIds
        .map((communication) => communication.id)
        .filter((id) => !excludedCommunicationIds.value.includes(id)),
      due_date: dueDate.value,
      company_id: selectedCompanyConfig.value.id,
      use_type_id: selectedCommunicationUseType.value.id,
      description: description.value,
    };
    console.log('payload');
    console.log(payload);
    const response = await $CommunicationProcessApiService.save(payload);
    if (response) {
      toast.success(t('common.correct_save'));
      navigateTo('/communication/process-communications/');
    } 
  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  getCompaniesConfig();
  await fetchConfigData('communication', 'communication-use-type', communicationUseTypes);
  selectedCommunicationUseType.value = communicationUseTypes.value.find(type => type.is_default) || null;
});

watch(() => props.communicationIds, (newVal) => {
  excludedCommunicationIds.value = [];
});

</script>

<template>
  <div class="region__content pr-1">
    <div class="h-full flex flex-col min-w-0 gap-2">
      <div class="flex justify-between items-center">
        <H1Region>{{ $t('customer_service_block.check_selected_comms') }}</H1Region>
      </div>

      <div
        class="my-4 mx-1 p-3 border-l-2 border-sky-500 rounded bg-sky-50 text-sky-500 grid grid-cols-[auto,1fr] gap-2">
        <div class="flex items-center">
          <Icon name="fa6-solid:info" class="text-sky-500" />
        </div>
        <div>
          <p class="text-sm font-medium">
            {{ t('informative_block.info_check_selected_comms') }}
          </p>
        </div>
      </div>

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_communications" @click.prevent="setActiveTab('communications')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'communications', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'communications' }"
            aria-current="page">
            <Icon name="fa6-solid:envelope" class="display-inline mr-2" />
            {{ $t("common.comms") }} ({{ communicationIds.length }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_config" @click.prevent="setActiveTab('config')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'config', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'config' }"
            aria-current="page" class="relative">
            <Icon name="fa6-solid:gear" class="display-inline mr-2" />
            {{ $t("common.settings") }}
            <span v-if="missingConfig"
              class="absolute top-1 right-1 w-3 h-3 bg-amber-400 rounded-full animate-ping opacity-75"></span>
          </a>
        </li>
      </AtomsTabs>

      <div v-show="activeTab === 'communications'" class="flex-1 min-h-0">
        <CheckCommunicationsProcessData :communication-ids="communicationIds" />
      </div>

      <div v-show="activeTab === 'config'" class="flex-1 min-h-[300px] rounded bg-white p-4 text-slate-500" :style="{
        minHeight: 'calc(100vh - 300px)',
        maxHeight: 'calc(100vh - 300px)',
      }">

        <div class="w-full">
          <div class="mt-2 grid grid-cols-2 gap-2">
            <div>
              <div>
                <label class="block font-medium text-slate-500 mb-2">
                  {{ t('customer_service_block.sender_company') }}<span class="text-red-500">*</span>
                </label>
                <v-select class="block w-full mr-2 required"
                  :disabled="loadingCompaniesConfig || companiesConfig.length == 0" :model-value="selectedCompanyConfig"
                  @update:modelValue="selectedCompanyConfig = $event;" :options="companiesConfig" />
              </div>
              <div class="mt-2">
                <label class="block font-medium text-slate-500 mb-2">
                  {{ t('common.send_date') }}<span class="text-red-500">*</span>
                </label>
                <AtomsInputDate v-model="dueDate" class="w-full" :label="''" />
              </div>
              <div>
                <label class="block font-medium text-slate-500 mb-2">
                  {{ t('common.use_type') }}<span class="text-red-500">*</span>
                </label>
                <v-select class="block w-full mr-2 required" :disabled="communicationUseTypes.length == 0"
                  :model-value="selectedCommunicationUseType"
                  @update:modelValue="selectedCommunicationUseType = $event"
                  :options="communicationUseTypes" />
              </div>
            </div>
            <div>
              <label class="block font-medium text-slate-500 mb-2">
                {{ t('common.description') }} <span class="text-red-500">*</span>
              </label>
              <textarea id="messageTextarea" v-model="description" class="input w-full h-48"
                :label="$t('common.description')" :required="true" />
            </div>
          </div>
        </div>

      </div>
    </div>
    <div class="my-2 pt-2 border-t border-slate-300 flex items-center justify-end">
      <button class="button-primary" :disabled="saving || !allowSave" @click="save">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
      </button>
    </div>
  </div>
</template>
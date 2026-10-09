<script setup>
// components/organisms/ContractRequestTypeRegion.vue
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

import ConfigList from '~/components/organisms/ConfigList.vue';

const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  invoice: Object
});

const emit = defineEmits(['show-subregion', 'changed']);
const { $MessageApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const invoice_data = ref(null)

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $MessageApiService.getDetail(props.id);
    data.value = result;

    invoice_data.value = props.invoice ? props.invoice : null

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}


watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});


onMounted(() => {
  getData();
});

// Subregion
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
}



</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('common.message') }}
        </H1Region>
        <!-- <H1Region class="mb-3">
          {{ $t('Missatge associat a ') }}
          <AtomsColorBadge v-if="invoice_data" :value="invoice_data.name" :color="invoice_data.color">
          </AtomsColorBadge>
          <span v-else>
            {{ data.invoices? data.invoices.length : 0 }}
            {{ $t(' factures') }}
          </span>
        </H1Region> -->

      </div>

      <div v-if="data" id="item_data" :data-rel="id">
        <div class="mb-3 grid grid-cols-2 gap-4">
          <FieldDetail :label="t('common.name')" :strong="true" :value="data.title">
            <strong class="text-sky-500">{{ data.title }}</strong>
          </FieldDetail>
        </div>
        
        <div class="mb-3 grid grid-cols-2 gap-4">
          <FieldDetail :label="t('common.start')" :strong="true" :value="data.start_at?formatDate(data.start_at):'-'">
          </FieldDetail>
          <FieldDetail :label="t('common.end')" :strong="true" :value="data.end_at?formatDate(data.end_at):'-'">
          </FieldDetail>
        </div>

        <hr class="my-2" />
        
        <div class="mb-3 gap-4">
          <fieldset>
            <legend class="mb-3 font-semibold pt-2">
              {{ t('customer_service_block.body') }}
              <span v-if="data.message_type" class="text-[10px] ml-2 text-slate-700 bg-yellow-50 rounded-md px-2 py-1 italic border border-slate-400"> 
                {{ data.message_type }}
              </span>
            </legend>
            <div v-if="data.content" class="p-2 border border-slate-300 rounded-lg w-full">
              {{ data.content }}
            </div>
            <div v-else class="p-2 border border-slate-300 rounded-lg w-full text-slate-500 italic">
              {{ $t('customer_service_block.no_content') }}
            </div>

          </fieldset>

        </div>
      </div>


    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ConfigList v-if="showRegionDetailComponent === 'ConfigList'" :title="$t('common.doc_types') + ': ' + data.name"
          entity="contract/contract-request-documentation-type" :hasColor="false" :hasMandatoryCheck="true"
          parent_entity="contract_request_type" :parent_id="props.id" @changed="handleDocumentChanged" />


      </div>
    </div>
  </div><!-- end region__content -->
</template>

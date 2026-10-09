<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import InvoicePaymentDetail from '../molecules/InvoicePaymentDetail.vue';
import FieldDetail from '../atoms/FieldDetail.vue'
import { checkPermission } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const router = useRouter();
const { $ReadingBatchTemplateApiService, $ReadingApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(false);
const showRegionDetailComponent = ref(null);

const getData = async () => {
  pending.value = true;
  error.value = null;
  
  try {
    const result = await $ReadingBatchTemplateApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

onMounted(async () => {
  objectPermissions.value = await checkPermission($ReadingApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

const editTemplate = function (id) {
  navigateTo('/reading/reading-batch-templates/edit/' + props.id);
}

</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.reading_batch_template') }}
        </H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ReadingBatchTemplateRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('common.template')}`" @click="editTemplate"></DropdownOption>
          <!-- <DropdownOption v-if="data.status?.token == status_pending_token" name="Confirmar Factura" @click="confirmInvoice"></DropdownOption> -->
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <div role="row" class="grid grid-cols-2">
          <FieldDetail :label='$t("common.code")' :value=data.token></FieldDetail>
          <FieldDetail :label='$t("common.name")' :value=data.name></FieldDetail>
        </div>
        <hr class="my-2" />
        <div role="row">
          <FieldDetail :label="$t('common.routes')" value="">
            <div class="ml-5 mt-2 space-y-1 divide-y divide-slate-300">
              <div v-for="route in data.routes" :key="route.id" class="grid grid-cols-[1fr,auto] gap-4 items-center">
                <span class="text-sm text-slate-700">{{ route.name }}</span>
                <span class="text-sm text-slate-500">{{ route.num_total_readings }} {{ $t('common.supplys') }}</span>
              </div>
            </div>
          </FieldDetail>
        </div>
        <!-- <AtomsTabs class="py-2">
          <li class="me-2 ">
            <a href="#tab_billings" @click.prevent="setActiveTab('billings')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'billings', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'billings' }">
              <Icon name="fa6-solid:clipboard" class="display-inline mr-2" /> {{ $t("Facturacions") }}
            </a>
          </li>
        </AtomsTabs>

        <div id="invoice_tabpanels">
          <section v-show="activeTab === 'billings'" role="tabpanel" id="tab_billings" class="bg-white antialiased">
            <div class="mt-2">
            </div>
          </section>
        </div> -->

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
      </div>
    </div>
  </div><!-- end region__content -->
</template>

<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import FieldDetail from '../atoms/FieldDetail.vue'
import { checkPermission } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';

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
const { $BillerApiService, $BillingApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const status_confirmed_token = ref(null);
const status_pending_token = ref(null);

const activeTab = ref('billings');
const SubRegion = ref(props.isSubRegionOpen);


const getData = async () => {
  pending.value = true;
  error.value = null;

  try {
    const result = await $BillerApiService.getDetail(props.id);
    data.value = result;
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

onMounted(async () => {
  objectPermissions.value = await checkPermission($BillingApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const editBiller = function (id) {
  navigateTo('/billing/biller/edit/' + props.id);
}

</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.biller') }}
        </H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${$t('common.modify')} ${$t('billing_block.biller')}`" @click="editBiller"></DropdownOption>
          <!-- <DropdownOption v-if="data.status?.token == status_pending_token" name="Confirmar Factura" @click="confirmInvoice"></DropdownOption> -->
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <div role="row" class="grid grid-cols-2">
          <FieldDetail :label='$t("common.code")' :value=data.token></FieldDetail>
          <FieldDetail :label='$t("common.name")' :value=data.name></FieldDetail>
        </div>
        <hr class="my-2" />
        <div role="row" class="grid grid-cols-2">
          <FieldDetail :label="$t('billing_block.action_range')" :value=data.period_type></FieldDetail>
          <FieldDetail :label='$t("billing_block.initial_month")' :value=data.initial_month></FieldDetail>

          <FieldDetail :label="$t('billing_block.action')" :value="data.num_routes > 0 ? t('billing_block.by_routes'): t('billing_block.all_supplies')"></FieldDetail>
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
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
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

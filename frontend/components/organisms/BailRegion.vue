<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ProductRegion from './ProductRegion.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import BailDetail from '../molecules/BailDetail.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import BailStatusChange from '../atoms/BailStatusChange.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const router = useRouter();
const { $BailApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('status_change');
const SubRegion = ref(props.isSubRegionOpen);
const objectPermissions = ref(null);
const status_returned_token = ref(null);
const status_pending_token = ref(null);

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $BailApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  try {
    status_returned_token.value = await $ConfigProjectApiService.get('bail_status_returned_token');
    status_pending_token.value = await $ConfigProjectApiService.get('bail_status_pending_token');
    const result = await $BailApiService.getDetail(props.id);
    data.value = result;

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const liquidateBail = async () => {
  if (!confirm(t("confirmation_text_block.confirm_liquidate_bail"))) return
  try {
    let save_data = {
      bail_ids: [props.id]
    }
    await $BailApiService.liquidate(save_data);
    await getData(false);
    emit('changed');

  } catch (err) {
    console.error(err);
  }
}

const cancelBail = async () => {
  if (!confirm(t("confirmation_text_block.confirm_cancel"))) return
  try {
    let save_data = {
      bail_ids: [props.id]
    }
    await $BailApiService.cancel(save_data);
    await getData(false);
    emit('changed');

  } catch (err) {
    console.error(err);
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return navigateTo('/');
  }
});

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const handleChange = () => {
  getData();
  emit('changed');
}

const handleClickChangeStatus = () => {
  closeSubRegion();
  showRegionDetailComponent.value = 'ChangeStatus';
  showSubRegion();
  emit('changed');
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
  emit('changed');
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}


const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('bail') }}</H1Region>
        <div class="relative">
          <OptionsDropdown v-if="objectPermissions?.can_change">
            <DropdownOption :disabled="data.status.token != status_pending_token"
              :name="t('billing_block.appropiate_bail')" @click="liquidateBail()"/>
            <DropdownOption :disabled="data.status.token != status_pending_token"
              :name="`${t('common.cancel')} ${t('bail').toLowerCase()}`" @click="cancelBail()"/>
          </OptionsDropdown>
        </div>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <BailDetail :data="data" :isSubRegion="isSubRegion" :isSubRegionOpen="isSubRegionOpen" @show-detail="showDetail"
          :disabled="true" @change="handleChange" />

        <AtomsTabs>
          <!-- pestanya de orders -->

          <li class="me-2">
            <a href="#tab_status_change" @click.prevent="setActiveTab('status_change')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'status_change', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.status_change") }} 
            </a>
          </li>

        </AtomsTabs>
        <div id="order_tabpanels">
          <!-- panells -->

          <section v-show="activeTab === 'status_change'" role="tabpanel" id="tab_status_change"
            class="bg-white antialiased">
            <div class="mt-2">
              <BailStatusChange :id="data.id" />
            </div>
          </section>

        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white ml-5 fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 ">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Subregions aqui -->

        <ProductRegion v-if="showRegionDetailComponent === 'ProductRegion'" :id="parseInt(regionDetailId)" :isSubRegion="true"/>
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="parseInt(regionDetailId)" :isSubRegion="true"/>
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="parseInt(regionDetailId)" :isSubRegion="true"/>
        <ChangeStatus v-if="showRegionDetailComponent === 'ChangeStatus'" entity="bail" parent_entity="bail"
          :id="props.id" :status="data.status?.id" module="contract" @changed="handleStatusChanged" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>

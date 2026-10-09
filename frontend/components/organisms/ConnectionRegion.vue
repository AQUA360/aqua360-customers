<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ConnectionDetail from '~/components/molecules/ConnectionDetail.vue';
import ConnectionDocumentsData from '~/components/molecules/ConnectionDocumentsData.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ConnectionRequestRegion from './ConnectionRequestRegion.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';
import OrderMiniDetail from '~/components/molecules/OrderMiniDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close']);

const objectPermissions = ref(null);
const router = useRouter();
const { $ConnectionApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('observations');
const observationNumber = ref(0)
const documentNumber = ref(0)
const ordersNumber = ref(0)

const SubRegion = ref(props.isSubRegionOpen);

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateOrdersCount = (num) => {
  ordersNumber.value = num;
}

const edit = () => {
  router.push(`/service/connections/edit/${props.id}`);
}

const remove = async () => {
  try {
    if (confirm(t('confirmation_text_block.confirm_delete'))) {
      await $ConnectionApiService.remove(props.id);
      emit('close');
    }
  } catch (err) {
    console.error(err);
  }
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ConnectionApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close');
    return
  }
  pending.value = true;
  error.value = null;
  try {
    const result = await $ConnectionApiService.getDetail(props.id);
    data.value = result;
    documentNumber.value = (result.documentation_files || []).filter(d => d.is_active !== false).length;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}


watch(() => props.id, () => {
  getData();
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close');
  }
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const showMap = () => {
  showRegionDetailComponent.value = "ShowMap"
  showSubRegion()
}

const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions.can_view" class="pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('connection') }}</H1Region>
        <OptionsDropdown v-if="!isSubRegion && objectPermissions.can_change" id="OrderRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('connection')}`" 
          @click="edit"></DropdownOption>
          <DropdownOption :name="t('common.delete')" @click="remove"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <ConnectionDetail :id="props.id" :data="data" @show-map="showMap()" :isSubRegion="isSubRegion" @show-detail="showDetail" @refresh="getData" />
        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.observations") }} ({{
              observationNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_documents" @click.prevent="setActiveTab('documents')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'documents', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'documents' }">
              <Icon name="fa6-solid:file" class="display-inline mr-2" /> {{ $t("common.docs") }} ({{ documentNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_orders" @click.prevent="setActiveTab('orders')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'orders', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders' }">
              <Icon name="fa6-solid:screwdriver-wrench" class="display-inline mr-2" /> {{ $t("work_orders") }} ({{
              ordersNumber }})
            </a>
          </li>
        </AtomsTabs>
        <div id="tabpanels">
          <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
            class="bg-white antialiased py-3">
            <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
              parent_entity="connection" :id="props.id" module="service"></MoleculesObservationList>
          </section>
          <section v-show="activeTab === 'documents'" role="tabpanel" id="tab_documents"
            class="bg-white antialiased py-3">
            <ConnectionDocumentsData v-if="data" :connection="data" @update-item="(updated) => { data = updated; documentNumber = (updated.documentation_files || []).filter(d => d.is_active !== false).length; }" />
          </section>
          <section v-show="activeTab === 'orders'" role="tabpanel" id="tab_orders"
            class="bg-white antialiased py-3">
            <OrderMiniDetail :connection_id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail"
              @update:count="updateOrdersCount" />
          </section>
        </div>
      </div>
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-full z-50"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <OrganismsMapRegion v-if="showRegionDetailComponent == 'ShowMap'" :longitude="parseFloat(data.longitude)"
          :latitude="parseFloat(data.latitude)" :address="data.address_complete"></OrganismsMapRegion>
        <ConnectionRequestRegion v-if="showRegionDetailComponent == 'ConnectionRequestRegion'" :id="regionDetailId"
          @show-subregion="showSubRegion" @changed="getData" />
        <OrderRegion v-if="showRegionDetailComponent == 'OrderRegion'" :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>

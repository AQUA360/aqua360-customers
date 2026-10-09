
<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OperatorDetail from '~/components/molecules/OperatorDetail.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const objectPermissions = ref(null);
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const router = useRouter();
const { $OperatorApiService } = useNuxtApp();
const { $OrderApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('orders');
const SubRegion = ref(props.isSubRegionOpen);
const observationNumber = ref(0)

const orders = ref([]);

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $OperatorApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;

  try {
    const result = await $OperatorApiService.getDetail(props.id);
    const result_order = await $OrderApiService.getAll('', [], 1, null, false, props.id);
    data.value = result;

    orders.value = [];

    result_order.results.forEach(function (item) {
      orders.value.push({
        id: item.id,
        token: item.token,
        type: item.type,
        status: item.status
      })
    })

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
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

onMounted(async() => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  await getData();
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

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  if (props.isSubRegion) {
    return 
  }
  
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const edit = function () {
  return navigateTo('/order/operators/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('operator') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions.can_change" id="OperatorRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('operator')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <div class="mb-3">
          <OperatorDetail :id="id" :data="data" />
          <hr class="my-2" />
        </div>

        <AtomsTabs>
          <!-- pestanya de orders -->
          <li class="me-2">
            <a href="#tab_orders" @click.prevent="setActiveTab('orders')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'orders', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders' }"
              aria-current="page">
              <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />{{ $t("work_orders") }} ({{
                orders?.length || 0 }})
            </a>
          </li>
        </AtomsTabs>
        <div id="cluster_tabpanels">
          <!-- panell de orders -->
          <section v-show="activeTab === 'orders'" role="tabpanel" id="tab_orders" class="bg-white antialiased py-3">
            <div v-if="orders.length != 0" class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="grid grid-cols-[30px,1fr,1fr,1fr] gap-3 text-base border-b items-center">
                <span class="p-2 pl-3 text-slate-600"></span>
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.identification') }} </span>
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.type') }} </span>
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.status') }} </span>
              </div>

              <div v-for="order in orders" :key="order.id"
                class="grid grid-cols-[30px,1fr,1fr,1fr] gap-3 text-base border-b items-center">
                <span></span>
                <span>
                  <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                    @click="showDetail('Order', order.id)">
                    <span class="text-slate-600 mr-1">{{ order.token }}</span>
                    <Icon :name="isSubRegion ? 'fa6-solid:external-link' : 'fa6-solid:eye'"
                      class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
                  </button>
                </span>
                <span class="p-2 pl-3 text-slate-600">{{ order.type?.name || '-' }}</span>
                <span class="p-2 pl-3 text-slate-600">{{ order.status?.name || '-' }}</span>
              </div>

            </div>

            <div v-else class="footering text-slate-500 p-2">
              {{ t('common.no_records') }}
            </div>
          </section>
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <!-- Subregions aqui -->
        <OrderRegion v-if="showRegionDetailComponent === 'Order'" :id="regionDetailId" :isSubRegion="true" />
        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div><!-- end region__content -->
</template>

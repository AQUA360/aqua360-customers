<script setup>
import { ref, onMounted } from 'vue';
import RouteSelect from '~/components/molecules/RouteSelect.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast();
const { $BillerApiService, $BillingApiService } = useNuxtApp();
const objectPermissions = ref(null);

const props = defineProps({
  id: {
    type: String,
    required: false,
  },
});

const getPermissions = async () => {
  try {
    const data = await $BillingApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    console.log(err)
  }
}

const is_active = ref(true);
const type = ref(null);
const types = ref([
  { code: 'mensual', label: t('date.monthly') },
  { code: 'bimestral', label: t('date.bimonthly') },
  { code: 'semestral', label: t('date.semestral') },
  { code: 'trimestral', label: t('date.trimestral') },
  { code: 'quadrimestral', label: t('date.quadrimestral') },
  { code: 'anual', label: t('date.annual') },
]);

const typeJumps = ref([
  { code: 'bimestral', num: 2 },
  { code: 'semestral', num: 6 },
  { code: 'trimestral', num: 3 },
  { code: 'quadrimestral', num: 4 },
  { code: 'anual', num: 12 },
])

const billingMonths = ref([]);

const month = ref({ code: 'jan', label: t('date.january') });
const months = ref([
  { code: 'jan', label: t('date.january') },
  { code: 'feb', label: t('date.february') },
  { code: 'mar', label: t('date.march') },
  { code: 'apr', label: t('date.april') },
  { code: 'may', label: t('date.may') },
  { code: 'jun', label: t('date.june') },
  { code: 'jul', label: t('date.july') },
  { code: 'aug', label: t('date.august') },
  { code: 'sep', label: t('date.september') },
  { code: 'oct', label: t('date.october') },
  { code: 'nov', label: t('date.november') },
  { code: 'dec', label: t('date.december') },
]);

const setBillingMonths = () => {
  billingMonths.value = [];

  let firstIndex = months.value.findIndex(m => m.code == month.value.code) + 1;
  let interval = typeJumps.value.find(j => j.code == type.value.code).num;

  if (firstIndex > interval) firstIndex -= interval;

  let diff = interval - firstIndex;

  let i = 1;
  months.value.forEach(m => {
    if ((i + diff) % interval == 0) {
      billingMonths.value.push(m.label);
    }
    i++;
  });
}

const loading = ref(true);

const showRegion = ref(false);
const billerType = ref('all');

const token = ref('')
const name = ref('')

const routes = ref([]);
const editingRoutes = ref(false);


const isSubRegionOpen = ref(false);

const openRouteRegion = () => {
  toggleRegion(true);
  editingRoutes.value = true;
}

const toggleRegion = (force) => {
  editingRoutes.value = false;
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const removeRoute = (item) => {
  routes.value = routes.value.filter(r => r.id != item.id);
}

const save = async () => {

  const routeIds = routes.value.map(r => r.id);

  const data = {
    id: props.id || null,
    token: token.value,
    name: name.value,
    period_type: type.value.code,
    initial_month: month.value.code,
    route_ids: routeIds
  }

  const response = await $BillerApiService.save(data)

  navigateTo('/billing/biller/');
}

const activate = async (active) => {
  const data = {
    id: props.id,
    is_active: active
  }
  let confirmText = active? t("confirmation_text_block.confirm_activate_biller") : t("confirmation_text_block.confirm_deactivate_biller");
  if (confirm(confirmText)) {
    const response = await $BillerApiService.save(data)
    navigateTo('/billing/biller/');
  }
}

const loadData = async () => {
  const res = await $BillerApiService.getDetail(props.id);
  name.value = res.name;
  token.value = res.token;
  routes.value = res.routes || [];

  if (routes.value.length == 0) billerType.value = 'all';
  else billerType.value = 'routes';

  const myType = types.value.find(t => t.code == res.period_type);
  if (myType) {
    type.value = myType;
  }

  const myMonth = months.value.find(m => m.code == res.initial_month);
  if (myMonth) {
    month.value = myMonth;
  }

  if (type.value.code != 'mensual') {
    setBillingMonths()
  }

  is_active.value = res.is_active;

  loading.value = false;
}

onMounted(async() => {
  await getPermissions();
  if (!objectPermissions.value?.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  if (props.id) {
    loadData();
  }
  else {
    loading.value = false;
  }
});


const updateSelected = (e) => {
  if (e.entity == 'type') {
    type.value = e.id;
  }
  else if (e.entity == 'month') {
    month.value = e.id;
  }

  if (type.value.code != 'mensual') {
    setBillingMonths()
  }

}

</script>

<template>
  <div class="text-base">


    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="objectPermissions?.can_change" class="border border-gray-300 rounded-b p-4 bg-white">

      <div class="grid grid-cols-2 gap-4">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" v-model="token" class="input" :disabled="!is_active" />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input" :disabled="!is_active" />
        </div>
        <div class="mb-2">
          <div class="flex">
            <label for="type" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('billing_block.billing_range')
              }} *</label>
          </div>
          <v-select class="block w-full mr-2 required" :model-value="type" :disabled="!is_active"
            @update:modelValue="updateSelected({ entity: 'type', id: $event })" :options="types"></v-select>
        </div>
        <div class="mb-2" v-if="type && type.code != 'mensual'">
          <div class="flex">
            <label for="month" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('billing_block.initial_month')
              }} *</label>
          </div>
          <v-select class="block w-full mr-2 required" :model-value="month" :disabled="!is_active"
            @update:modelValue="updateSelected({ entity: 'month', id: $event })" :options="months"></v-select>
        </div>
        <div v-if="type && type.code != 'mensual'" class="flex">
          <div class="text-sm font-medium text-slate-500 mb-2 mr-4">{{ $t('date.months') }}:</div>

          <div class="flex">
            <span v-for="month, idx in billingMonths" class="mr-2">{{ month }}{{ idx != billingMonths.length - 1 ? ',' :
              '' }}</span>
          </div>

        </div>
        <div class="footering col-span-2">

          <div class="flex items-center mb-2">
            <label class="mr-4">
              <input type="radio" v-model="billerType" value="all" :disabled="!is_active" /> {{ t('billing_block.all_supplies') }}
            </label>
            <label>
              <input type="radio" v-model="billerType" value="routes" :disabled="!is_active" /> {{ t('billing_block.by_routes') }}
            </label>
          </div>

          <div v-if="billerType != 'all'" :class="{ 'mt-1': routes.length != 0 }" class="text-gray-900 divide-y rounded shadow">
            <div v-if="routes.length != 0" class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
              <span class="p-1 text-slate-400">
                {{ t('common.code') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('common.name') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('service_block.zone') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('readings') }}
              </span>
            </div>
            <div v-for="item in routes" class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
              <div class="p-2 text-slate-800">{{ item.token }}</div>
              <div class="p-2 text-slate-800 relative">
                {{ item.name }}
              </div>
              <div class="p-2 text-slate-800 relative">
                {{ item.zone_name }}
              </div>
              <div class="p-2 text-slate-800 relative">
                {{ item.num_total_readings }}
                <button @click="removeRoute(item)"
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering flex ">
              <button @click="openRouteRegion" :disabled="!is_active"
                class="display-block block w-full px-1 py-1 text-base shadow rounded text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:pencil" class="text-slate-400 mx-2" /> {{ $t('common.select') }} {{ $t('common.routes') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="col-span-3 flex flex-row-reverse mt-4" v-if="!is_active">
        <button @click="activate(true)" class="button-primary">
          <Icon name="fa6-solid:check" />&nbsp; {{ t('common.activate') }}
        </button>

      </div>
      <div class="col-span-3 flex flex-row-reverse mt-4" v-if="is_active">
        <button @click="save" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
        </button>
        <button @click="activate(false)" class="button-delete mr-4" v-if="props.id">
          <Icon name="fa6-solid:x" />&nbsp; {{ t('common.deactivate') }}
        </button>
      </div>

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">

        <RouteSelect v-model="routes" @item-clicked="onSelectedRoute" v-if="editingRoutes" />

        <!-- <BillingBatchTemplateSelect v-model="batch_templates" @item-clicked="onSelectedTemplate" v-if="selectingTemplates" />
        <BillingBatchTemplateEdit @on-saved="onSaved" @on-removed="onRemoved" @show-subregion="handleSubRegionEvent" :id="templateId" v-if="editingTemplate" /> -->
      </div>
    </div>
  </div>
</template>
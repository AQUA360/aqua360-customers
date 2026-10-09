<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import RouteSelect from '~/components/molecules/RouteSelect.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const { $BillingBatchTemplateApiService } = useNuxtApp();

const props = defineProps({
  id: {
    type: Number,
    required: false,
  },
});

const emit = defineEmits(['show-subregion', 'on-saved']);

const template = ref(null);
const routes = ref([]);

const name = ref('')
const token = ref('')

const loading = ref(true);
const saving = ref(false);

const subRegion = ref(false);
const editingRoutes = ref(false);

const toggleSubRegion = (e) => {
  toggleRegion(e);
  editingRoutes.value = e;
  emit('show-subregion', e);
}

const onSelectedRoute = () => {
  toggleRegion(true);
  editingRoutes.value = true;
}

const toggleRegion = (force) => {
  editingRoutes.value = false;
  subRegion.value = force !== undefined ? force : !subRegion.value;
}

const removeRoute = (item) => {
  routes.value = routes.value.filter(r => r.id != item.id);
}

const save = async () => {
  saving.value = true;

  const route_ids = routes.value.map(r => r.id);

  const selectedOptions = {
    id: props?.id || null,
    token: token.value,
    name: name.value,
    route_ids: route_ids
  };

  const res = await $BillingBatchTemplateApiService.save(selectedOptions);

  emit('on-saved', res);

  saving.value = false;
  // return navigateTo('/service/routes/')

}

const remove = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    const res = await $BillingBatchTemplateApiService.remove(props.id);
    emit('on-removed', props.id);
    saving.value = false;
  }
}



const loadData = async () => {
  template.value = await $BillingBatchTemplateApiService.getDetail(props.id);
  name.value = template.value.name;
  token.value = template.value.token;

  routes.value = template.value.routes;

  loading.value = false;
}

onMounted(() => {
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
}

</script>

<template>
  <div class="text-base">
    <div class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': subRegion }">
      <div class="mb-4">
        <H1>{{ props.id ? $t('billing_block.edit_billing_batch_template') : $t('billing_block.new_billing_batch_template') }}</H1>
      </div>

      <!-- Contingut del Pas Actual -->
      <div v-if="loading">
        <AppLoading :text="$t('common.loading')" />
      </div>
      <div v-else class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="grid grid-cols-2 gap-4">

          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
            <input type="text" v-model="token" class="input" />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
            <input type="text" v-model="name" class="input" />
          </div>

          <div class="footering col-span-2">
            <div :class="{ 'mt-1': routes.length != 0 }" class="text-gray-900 divide-y rounded shadow">
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
              <div class="footering">
                <button @click="toggleSubRegion(true)"
                  class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                  <Icon name="fa6-solid:pencil" class="text-slate-400 mx-2" /> {{ $t('common.select') }} {{ $t('common.routes') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="col-span-3 flex flex-row-reverse mt-4">
          <button @click="save" class="button-primary" :disabled="saving">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
          </button>
          <button v-if="props.id" @click="remove" class="button-default mr-4" :disabled="saving">
            <Icon name="fa6-solid:trash" />&nbsp; {{ t('common.delete') }}
          </button>
        </div>

      </div><!--end contingut pas actual -->
    </div>

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->

    <div v-if="subRegion == true" role="region" id="subregion"
      class="h-full ml-6 border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': subRegion, 'translate-x-full': !subRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleSubRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <RouteSelect v-model="routes" @item-clicked="onSelectedRoute" v-if="editingRoutes" />
      </div>
    </div>
  </div>
</template>
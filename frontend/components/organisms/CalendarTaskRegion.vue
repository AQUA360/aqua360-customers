<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import CalendarTaskDetail from '../molecules/CalendarTaskDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import CalendarTaskEdit from '../molecules/CalendarTaskEdit.vue';
import ContractRegion from './ContractRegion.vue';

const { t } = useI18n();

const props = defineProps({
  current_date: String,
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed']);

const router = useRouter();
const { $CalendarTaskApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $CalendarTaskApiService.getDayTasks(props.current_date);
    data.value = result.results;
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
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const openNewCalendarTask = function (item_id = null) {
  closeSubRegion();
  showRegionDetailComponent.value = 'CalendarTaskEdit';
  regionDetailId.value = item_id;
  showSubRegion();
}

const showDetail = function (component, id) {
  closeSubRegion();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const refresh = async (close = true) => {
  await getData()
  if (close) closeSubRegion()
  emit('changed')
}

watch(() => props.current_date, () => {
  getData();
});

onMounted(() => {
  getData();
});

</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('dashboard.today_tasks') }}
          <span class="text-slate-400 text-sm ml-2">
            {{ formatDate(props.current_date) }}
          </span>
        </H1Region>
        <OptionsDropdown id="CalendarTaskRegionOptions">
          <DropdownOption :name="t('dashboard.new_task')" @click="showDetail('CalendarTaskEdit', null)"></DropdownOption> 
        </OptionsDropdown>
      </div>
      <!-- <div class="h-[70vh] customers-shadow rounded my-2 overflow-y-auto"> -->
      <div class="h-[80vh] border-b my-2 overflow-y-auto">
        <div v-for="item in data" :key="item.id" class="my-1">
          <CalendarTaskDetail :data="item" @edit="showDetail" @show-detail="showDetail" />
        </div>
  
        <div v-if="data.length === 0" class="flex font-bold text-slate-700 justify-center items-center bg-slate-100 rounded-md p-4">
          {{ $t("common.no_data") }}
        </div>
      </div>

      <!-- <div>
        <ButtonSeleccio @click="openNewCalendarTask">{{ $t('Afegeix una nova tasca') }}</ButtonSeleccio>
      </div> -->

    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white flex flex-col fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <CalendarTaskEdit v-if="showRegionDetailComponent === 'CalendarTaskEdit'" :current_date="current_date" :id="regionDetailId" @change="refresh" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId" :isSubRegion="true" @changed="refresh" />
      </div>
    </div>
  </div>
</template>

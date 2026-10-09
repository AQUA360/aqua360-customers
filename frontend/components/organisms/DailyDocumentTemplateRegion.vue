<script setup>
import { useRouter } from 'vue-router';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import DailyDocumentTemplateDetail from '../molecules/DailyDocumentTemplateDetail.vue';
import DailyDocumentTemplateEdit from './DailyDocumentTemplateEdit.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});


const emit = defineEmits(['show-subregion', 'changed', 'close-subregion', 'refresh-list']);
const toast = useToast();
const router = useRouter();
const { $DailyDocumentTemplateApiService, $ConfigProjectApiService, $CommunicationApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const objectPermissions = ref(null);

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $CommunicationApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  error.value = null;
  try {
    const result = await $DailyDocumentTemplateApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    console.error(err)
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const refresh = async (close = true) => {
  if (close) closeSubRegion()
  await getData()
  emit('changed')
}

const deactivate = async () => {
  try {
    const payload = {
      id: props.id,
      is_active: !data.value.is_active
    }
    await $DailyDocumentTemplateApiService.save(payload);
    await getData();
    emit('changed');
  } catch (err) {
    console.error(err)
  }
}


watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

</script>

<template>
  <div class="region__content h-full" @click.stop>
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48%]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <H1Region class="">{{ $t('statistics_block.daily_document_template') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="CommunicationRegionOptions">
          <DropdownOption :name="`${t('common.modify')}`" @click="showDetail('DailyDocumentTemplateEdit', props.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ t('common.modify') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.deactivate')}`" @click="deactivate">
            <Icon name="fa6-solid:circle-xmark" class="display-inline mr-2" /> {{ data.is_active ?
              t('common.deactivate') : t('common.activate') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <DailyDocumentTemplateDetail :id="props.id" :data="data" @show-detail="showDetail" />
      </div>

    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48%] z-10"
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
        <DailyDocumentTemplateEdit v-if="showRegionDetailComponent === 'DailyDocumentTemplateEdit'" :id="regionDetailId"
          @changed="getData" @close-subregion="closeSubRegion" />
      </div>
    </div>
  </div>
</template>
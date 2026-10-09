<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import UserDetail from '../molecules/UserDetail.vue';
import GroupRegion from './GroupRegion.vue';
import { usePermissions } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { permissions, loading } = usePermissions();
const toast = useToast();
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const router = useRouter();
const { $UserApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('contracts');
const SubRegion = ref(props.isSubRegionOpen);

const getData = async () => {
  pending.value = true;
  if (!permissions?.value.permissions?.view_user) {
    emit('close-subregion');
    return
  }
  try {
    const result = await $UserApiService.getDetail(props.id);
    data.value = result;

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }

}

watch(() => props.id, () => {
  if (!permissions?.value.permissions?.view_user) {
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
  while (loading.value) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!permissions?.value.permissions?.view_user){
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return
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
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const edit = function () {
  return navigateTo('/user/users/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content">
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
          {{ $t('user') }}
        </H1Region>
        <OptionsDropdown v-if="permissions?.permissions?.change_user" id="GroupRegionOptions">
          <DropdownOption :name="t('common.modify') + ' ' + t('user')" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <UserDetail :id="data.id" :data="data" :isSubRegion="isSubRegion" @show-subregion="showDetail" />
      </div>
    </div>

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <GroupRegion v-if="showRegionDetailComponent == 'GroupRegion'" :id="regionDetailId"
        :isSubRegion="SubRegion" />
      </div>
    </div>
  </div>
</template>

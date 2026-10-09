<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { usePermissions } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const toast = useToast();
const { permissions: userPermissions, loading } = usePermissions();


const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const router = useRouter();
const { $GroupApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('contracts');
const SubRegion = ref(props.isSubRegionOpen);
const mainPermissions = ref([]);
const permissions = ref({});

const permissionDisplayData = computed(() => {
  let permissionTypes = [];

  mainPermissions.value.forEach(type => {
    if (!type.is_default) {
      permissionTypes.push({
        label: type.name,
        viewKey: type.view_key,
        changeKey: type.change_key
      });
    }
  });

  let data = permissionTypes.map(type => ({
    ...type,
    hasView: permissions.value[type.viewKey] || false,
    hasChange: permissions.value[type.changeKey] || false,
    hasAny: permissions.value[type.viewKey] || permissions.value[type.changeKey] || false
  }))
  return data;
});

const getData = async () => {
  pending.value = true;
  if (!userPermissions?.value.permissions?.view_user) {
    emit('close-subregion');
    return
  }

  try {
    const result = await $GroupApiService.getDetail(props.id);
    data.value = result;
    permissions.value = result.permissions;

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }

}

const getMainPermissions = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('coredata/main-permission');
    mainPermissions.value = response.results;
  } catch (error) {
    console.error(error);
  }
}

watch(() => props.id, () => {
  if (!userPermissions?.value.permissions?.view_user) {
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
  if (!userPermissions?.value.permissions?.view_user){
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return
  } 
  await getMainPermissions();
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
  return navigateTo('/user/groups/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

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
        <H1Region class="mb-3">
          {{ $t('group') }}
        </H1Region>
        <OptionsDropdown v-if="userPermissions?.permissions?.change_user" id="GroupRegionOptions">
          <DropdownOption :name="t('common.modify') + ' ' + t('group')" @click="edit"></DropdownOption>
          <DropdownOption :name="t('common.check') + ' ' + t('users')" :disabled="isSubRegion" @click="showDetail('UsersRegion', data.id)">
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <div class="grid grid-cols-2 gap-2 items-center">
          <FieldDetail :label='$t("common.name")' :value=data.name />
          <button :disabled="isSubRegion" class="enabled:button-default flex items-center gap-2"
            @click="showDetail('UsersRegion', data.id)">
            <Icon name="fa6-solid:users-gear" />
            {{ $t("user_group.users_in_group") }} ({{ data.users.length }})
          </button>
        </div>

        <hr class="my-4" />

        <div class="space-y-3">
          <h3 class="text-sm font-semibold text-slate-700 uppercase tracking-wide">{{ $t("permissions") }}</h3>

          <div class="space-y-2">
            <div v-for="permission in permissionDisplayData" :key="permission.key" class="bg-slate-50 border border-slate-200 rounded-lg p-3 grid grid-cols-2 gap-3 items-center">
              <div class="items-center">
                <span class="text-sm font-medium text-slate-800">{{ t(permission.label) }}</span>
              </div>
              <div class="flex justify-between gap-3 text-xs">
                <div class="items-center grid grid-cols-2 gap-2">
                  <span class="text-slate-600">{{ $t("common.check") }}</span>
                  <AtomsColorBadge :value="permission.hasView ? t('common.yes') : t('common.no')"
                    :color="permission.hasView ? 'green' : 'red'" />
                </div>
                <div class="items-center grid grid-cols-2 gap-2">
                  <span class="text-slate-600">{{ $t("common.modification") }}</span>
                  <AtomsColorBadge :value="permission.hasChange ? t('common.yes') : t('common.no')"
                    :color="permission.hasChange ? 'green' : 'red'" />
                </div>
              </div>
            </div>
          </div>
        </div>

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
        <MoleculesGroupUsersRegion v-if="showRegionDetailComponent == 'UsersRegion'" :users="data.users"
          :group_name="data.name" />
      </div>
    </div>
  </div>
</template>

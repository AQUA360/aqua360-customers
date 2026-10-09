<script setup>
import { ref, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import H1Region from '../atoms/H1Region.vue';

const props = defineProps({
  permissions: Array,
  mainPermissions: Array,
  group_name: String,
  group_id: String,
});

const { t } = useI18n();
const emit = defineEmits(['save']);
const { $ConfiglistApiService } = useNuxtApp();
const toast = useToast();
const localPermissions = ref([]);
const defaultPermission = ref(null);
const changePermissions = ref(null);
const loadingChangePermissions = ref(false);
const affectedData = ref([])

const showInfo = ref(true);
const showWarning = ref(true);

const save = async () => {
  emit('save', localPermissions.value);
}

const getData = () => {
  localPermissions.value = props.permissions;
  defaultPermission.value = props.mainPermissions.find(perm => perm.is_default);
  /* for (let permission of localPermissions.value) {
    let affectedData = props.mainPermissions.find(perm => perm.change_key == permission.changeKey).affected_data;
    permission.affected_data = affectedData;
  } */
}

const openChangePermissions = async (changeKey) => {
  if (changePermissions.value == changeKey) {
    changePermissions.value = null;
    affectedData.value = [];
    return;
  }
  loadingChangePermissions.value = true;
  changePermissions.value = changeKey;
  let permission = localPermissions.value.find(perm => perm.changeKey == changeKey);
  const mainPerm = props.mainPermissions.find(perm => perm.change_key == changeKey);
  permission.affected_data = mainPerm ? (mainPerm.affected_data || []) : [];
  affectedData.value = permission.affected_data;
  for (const data of affectedData.value) {
    if (props.group_id) {
      await getDataPermission(data);
    }
  }
  loadingChangePermissions.value = false;
}

const getDataPermission = async (data) => {
  if (data?.app) {
    if (data.can_change == true || data.can_change == false) {
      return;
    }
    try {
      const response = await $ConfiglistApiService.getData(`${data.app}/permissions/?id=${props.group_id}`, false);
      data.can_change = response.can_change;
    } catch (error) {
      console.error(error);
    }
  }
}

const checkChange = (permission) => {
  if (permission.hasChange && !permission.hasView) {
    permission.hasView = true;
    permission.hasAny = true;
  }
  if (!permission.hasChange) {
    changePermissions.value = null;
  }
}

const checkView = (permission) => {
  if (!permission.hasView) {
    permission.hasChange = false;
    changePermissions.value = null;
  }
  permission.hasAny = permission.hasView;
}

onMounted(async () => {
  getData()
});

watch(() => props.permissions, (newVal) => {
  getData()
}, { deep: true });

</script>

<template>
  <div class="region__content">

    <div>
      <div class="flex items-center justify-between gap-2 mb-3">
        <H1Region>{{ $t('permissions') }}</H1Region>
        <AtomsColorBadge :color="'blue'" :value="group_name" />
      </div>

      <div v-if="defaultPermission"
        class="flex items-center italic justify-between mb-1 px-3 text-slate-300 py-2.5 bg-slate-50 border border-slate-200 rounded-lg shadow-sm">
        <div class="flex items-center gap-2.5 min-w-0 flex-1">
          <abbr :title="defaultPermission.affected_data.map(item => item.name).join(', ')" class="flex-shrink-0">
            <Icon name="fa6-solid:circle-info" class="w-3 h-3" />
          </abbr>
          <span class="font-medium truncate">
            {{ t(defaultPermission.name) }}
          </span>
        </div>
        <div class="flex items-center gap-4 ml-4">
          <label class="flex items-center gap-2 cursor-not-allowed opacity-70">
            <input type="checkbox" :checked="true" :disabled="true"
              class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded " />
            <span class="text-sm font-medium text-slate-600">
              {{ t('common.check') }}
            </span>
          </label>
          <label class="flex items-center gap-2 cursor-not-allowed opacity-70">
            <input type="checkbox" :checked="true" :disabled="true"
              class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded " />
            <span class="text-sm font-medium text-slate-600">
              {{ t('common.modification') }}
            </span>
          </label>
        </div>
      </div>
      <span v-if="defaultPermission" class="m-1 px-2 border border-sky-500 bg-sky-50 rounded text-sky-500">
        {{ t('user_group.default_permissions') }}
      </span>

      <div v-if="localPermissions.length > 0 && mainPermissions.length > 0" class="space-y-1.5 mt-3">
        <div v-for="permission in mainPermissions.filter(perm => !perm.is_default)">
          <div
            class="flex items-center justify-between px-3 py-2.5 bg-white border border-slate-200 rounded-lg shadow-sm">
            <div class="flex items-center gap-2.5 min-w-0 flex-1">
              <abbr v-if="permission.affected_data && permission.affected_data.length" :title="permission.affected_data.map(item => t(item.name)).join(', ')" class="flex-shrink-0">
                <Icon name="fa6-solid:circle-info" class="text-slate-400 w-3 h-3" />
              </abbr>
              <span class="font-medium text-slate-700 truncate">
                {{ t(permission.name) }}
              </span>
            </div>
            <div class="flex items-center gap-4 ml-4">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox"
                  @change="checkView(localPermissions.find(perm => perm.viewKey == permission.view_key))"
                  v-model="localPermissions.find(perm => perm.viewKey == permission.view_key).hasView"
                  class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded" />
                <span class="text-sm font-medium text-slate-600">
                  {{ t('common.check') }}
                </span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox"
                  @change="checkChange(localPermissions.find(perm => perm.changeKey == permission.change_key))"
                  v-model="localPermissions.find(perm => perm.changeKey == permission.change_key).hasChange"
                  class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded" />
                <span class="text-sm font-medium text-slate-600">
                  {{ t('common.modification') }}
                </span>
              </label>
              <button v-if="permission.affected_data && permission.affected_data.length" :disabled="!localPermissions.find(perm => perm.viewKey == permission.view_key).hasChange"
                @click="openChangePermissions(permission.change_key)"
                class="disabled:opacity-30 disabled:cursor-not-allowed">
                <Icon name="fa6-solid:chevron-down" class="transition-all duration-300 ease"
                  :class="changePermissions == permission.change_key ? 'rotate-180' : ''" />
              </button>
            </div>
          </div>

          <div v-if="changePermissions == permission.change_key" class="m-2 rounded bg-sky-50 p-2">
            <p class="text-sm font-medium text-slate-500 mb-1 text-right">
              {{ t('user_group.mod_permissions') }}
            </p>
            <div v-if="loadingChangePermissions" class="flex items-center justify-center">
              <Icon name="fa6-solid:spinner" class="animate-spin" />
            </div>
            <div v-else class="flex items-center gap-2 grid grid-cols-2">
              <div v-for="data in affectedData" class="flex items-center gap-2">
                <input type="checkbox" v-model="data.can_change"
                  class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded" />
                <span class="text-sm font-medium text-slate-600">
                  {{ t(data.name) }}
                </span>
              </div>
              <div v-if="permission.all_recommended" class="col-span-full px-3 rounded-md bg-orange-50 border border-orange-500 text-orange-500">
                <p>
                  {{ t('user_group.all_data_tip') }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="showWarning" class="my-2 px-3 py-1 border border-orange-500 bg-orange-50 rounded text-orange-500 grid grid-cols-[1fr,auto]">
        <span>
          {{ t('warning_block.warning_tip') }}
        </span>
        <button @click="showWarning = false" class="text-orange-500 underline pl-2"><Icon name="fa6-solid:xmark" /></button>
      </div>
      <div v-if="showInfo" class="my-2 px-3 py-1 border border-sky-500 bg-sky-50 rounded text-sky-500 grid grid-cols-[1fr,auto]">
        <span>
          {{ t('user_group.info_tip') }}
        </span>
        <button @click="showInfo = false" class="text-sky-500 underline pl-2"><Icon name="fa6-solid:xmark" /></button>
      </div>

      <hr class="mb-2" />
      <div class="flex flex-row-reverse gap-3 mt-4">
        <button @click="save" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp;{{ $t('common.save') }}
        </button>
      </div>
    </div>
  </div>


</template>

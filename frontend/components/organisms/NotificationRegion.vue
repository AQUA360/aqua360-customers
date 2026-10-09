<script setup>
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useSidebarStore } from '~/stores/useNavSideBar';
import H1Region from '~/components/atoms/H1Region.vue';
import { format } from 'date-fns';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();

const props = defineProps({
});

const emit = defineEmits(['show-subregion', 'changed']);
const router = useRouter();
const { $NotificationApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref([]);
const hoveredNotificationId = ref(null);
const notificationFilterOpen = ref(false);
const is_active = ref(true);
const is_seen = ref(null);
const seen_by_user = ref(false);

const page = ref(1);
const pageSize = 15;
const hasNextPage = ref(true);
const loadingMore = ref(false);
const allDataLoaded = ref(false);

const sidebarStore = useSidebarStore();
const scrollPosition = ref(0); 
const scrollContainer = ref(null); 

const username = ref(null);

if (process.client) {
    username.value = localStorage.getItem('user_username') || '';
}

const getData = async (restart = false) => {
  pending.value = true;
  loadingMore.value = true; 
  if (restart) data.value = [];

  let newNotifications = await $NotificationApiService.checkNewNotifications();
  sidebarStore.newNotificationsFound(newNotifications);
  
  try {
    //CHECK IF DATA SHOULD BE GROUPED
    let response = await $NotificationApiService.getAll('', [], page.value, is_seen.value, is_active.value);
    if (response.results && response.results.length > 0) {
      if (response.next == null) {
        hasNextPage.value = false;
      }
      const newData = response.results;
      data.value = data.value.concat(newData);
      if (response.results.length < pageSize || !hasNextPage.value) {
        allDataLoaded.value = true;
      } else {
        page.value++;
      }
    } else {
      allDataLoaded.value = true;
    }
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
    loadingMore.value = false; // Set loadingMore to false after fetching data
    nextTick(() => {
      if (scrollContainer.value) {
        scrollContainer.value.scrollTop = scrollPosition.value;
      }
    });
  }
};

const markAllRead = async () => {
  let save_data = {
    id: data.value[0].id,
    is_seen: true,
    handle_all: true,
  };
  await $NotificationApiService.save(save_data);
  getData(true);
};

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  scrollPosition.value = scrollTop; // Update the scroll position
  if (!hasNextPage.value || loadingMore.value) return;
  if (scrollHeight - scrollTop <= clientHeight + 50) {
    getData();
  }
};

const deactivateAll = async () => {
  let save_data = {
    id: data.value[0].id,
    is_active: false,
    handle_all: true,
  };
  await $NotificationApiService.save(save_data);
  getData(true);
};
const closeNotifications = () => {
  sidebarStore.closeNotifications();
};

const hoverNotification = (result) => {
  hoveredNotificationId.value = result.id;
};

const openNotificationsFilter = () => {
  notificationFilterOpen.value = !notificationFilterOpen.value;
};

const filterNotifications = (filter) => {
  page.value = 1;
  data.value = [];
  switch (filter) {
    case 'no_archived':
      is_active.value = true;
      is_seen.value = null;
      break;
    case 'unread':
      is_active.value = true;
      is_seen.value = false;
      break;
    case 'archived':
      is_active.value = false;
      is_seen.value = null;
      break;
    case 'all':
      is_active.value = null;
      is_seen.value = null;
      break;
  }
  getData(true);
  notificationFilterOpen.value = false;
};

const redirectNotification = async (result) => {
  if (!result) return;
  let save_data = {
    id: result.id,
    is_seen: true,
  };
  await $NotificationApiService.save(save_data);
  closeNotifications();
  if (result.object_id) {
    // For orders, open in lateral panel instead of edit page
    if (result.module === 'order' && result.entity === 'orders') {
      return navigateTo('/' + result.module + '/' + result.entity + '?id=' + result.object_id);
    }
    return navigateTo('/' + result.module + '/' + result.entity + '/edit/' + result.object_id);
  } else {
    if (result?.module && result?.entity) {
      return navigateTo('/' + result.module + '/' + result.entity);
    } else {
      return navigateTo('/')
    }
  }
};

const markNotification = async (result) => {
  let save_data = {
    id: result.id,
    is_seen: !result.is_seen,
  };
  await $NotificationApiService.save(save_data);
  getData(true);
};

const activateNotification = async (result) => {
  let save_data = {
    id: result.id,
    is_active: !result.is_active,
  };
  await $NotificationApiService.save(save_data);
  getData(true);
};

getData();
</script>

<template>
  <div class="region__content h-full" @click="notificationFilterOpen = false">
    <div v-if="pending && !loadingMore">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else>
      <div class="px-5 flex justify-between relative">
        <div class="grid grid-cols-[auto,1fr] gap-3 items-center">
          <H1Region class="mb-3">{{ $t('dashboard.notifications') }}</H1Region>
        </div>
        <div class="flex items-center">
          <div class="mr-5 relative" @click.stop>
            <button @click="openNotificationsFilter" class="relative">
              <abbr :title="t('common.filter')">
                <Icon name="fa:filter" class="text-slate-500 text-xs mb-2" />
              </abbr>
            </button>
            <div v-if="notificationFilterOpen"
              class="z-10 text-sm absolute top-4 right-0 bg-white p-2 rounded-md customers-shadow w-[250px]">
              <button class="grid grid-cols-[20px,1fr] block w-full text-left hover:bg-slate-100 p-1 items-center"
                :class="{ 'bg-slate-100': is_active && is_seen == null }" @click="filterNotifications('no_archived')">
                <Icon name="fa6-solid:envelope-open" class="text-slate-500 text-sm mr-1 p-1" />
                {{ t('dashboard.show_read_and_unread') }}
              </button>
              <button class="grid grid-cols-[20px,1fr] block w-full text-left hover:bg-slate-100 p-1 items-center"
                :class="{ 'bg-slate-100': is_active && !is_seen && is_seen != null }"
                @click="filterNotifications('unread')">
                <Icon name="fa6-solid:envelope-circle-check" class="text-slate-500 text-sm mr-1 p-1" />
                {{ t('dashboard.show_unread') }}
              </button>
              <button class="grid grid-cols-[20px,1fr] block w-full text-left hover:bg-slate-100 p-1 items-center"
                :class="{ 'bg-slate-100': !is_active && is_active != null && is_seen == null }"
                @click="filterNotifications('archived')">
                <Icon name="fa6-solid:box-archive" class="text-slate-500 text-sm mr-1 p-1" />
                {{ t('dashboard.show_archived') }}
              </button>
              <button class="grid grid-cols-[20px,1fr] block w-full text-left hover:bg-slate-100 p-1 items-center"
                :class="{ 'bg-slate-100': is_active == null && is_seen == null }" @click="filterNotifications('all')">
                <Icon name="fa6-solid:align-left" class="text-slate-500 text-sm mr-1 p-1" />
                {{ t('dashboard.show_all_notifications') }}
              </button>
            </div>
          </div>
          <OptionsDropdown v-if="is_active && is_seen == null" id="OrderRegionOptions">
            <DropdownOption :name="t('dashboard.mark_all_read')" @click="markAllRead" />
            <DropdownOption :name="t('dashboard.archive_all')" @click="deactivateAll" />
          </OptionsDropdown>
          <!-- <Icon v-else name="fa6-solid:xmark" class="text-slate-500  absolute top-0 items-end right-0 mr-2 mt-1" /> -->
          <svg v-else class="w-4 h-4 absolute top-0 items-end right-0 mr-2 mt-1 opacity-25" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor"
            viewBox="0 0 16 3">
            <path
              d="M2 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm6.041 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM14 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z" />
          </svg>
        </div>
      </div>

      <div v-if="data.length > 0" class="overflow-y-auto scrollbar-hide h-[90vh]" @scroll="onScroll"
        ref="scrollContainer">
        <ul>
          <li v-for="(result, index) in data" :key="index" @click="redirectNotification(result)"
            @mouseenter="hoverNotification(result)" @mouseleave="hoveredNotificationId = null"
            class="relative group py-1 hover:bg-slate-100 cursor-pointer" :class="{
              'bg-sky-50': !result.read_by.map(user => user.username).includes(username),
              'italic opacity-80': result.read_by.map(user => user.username).includes(username),
              'bg-slate-100': result.archived_by.map(user => user.username).includes(username)
            }">
            <div class=" px-3 py-1">
              <div class="font-semibold text-slate-800">
                <div class="grid grid-cols-[1fr,auto] gap-2">
                  <p class="font-bold text-slate-800 text-sm pb-2">
                    <Icon v-if="result.archived_by.map(user => user.username).includes(username)" name="fa6-solid:box-archive" class="text-slate-500 text-xs mr-2" />
                    {{ result.name }}
                  </p>

                  <div class="text-xs text-slate-400 float-right">
                    <TimeRelative :datetime="result.created_at" />
                  </div>
                </div>
                <p class="text-slate-400 text-xs px-2">
                  {{ result.description }}
                </p>
              </div>
            </div>
            <div v-if="hoveredNotificationId === result.id"
              class="absolute p-3 top-3 right-0 text-xs text-slate-400 float-right mr-3 opacity-0 transition-all duration-300 group-hover:opacity-100"
              @click.stop="redirectNotification(null)">
              <div class="bg-white rounded-md customers-shadow p-1 flex items-center">
                <button v-if="result.read_by.map(user => user.username).includes(username)" class="default-xs h-6 w-6 rounded full hover:bg-slate-200"
                  @click="markNotification(result)">
                  <abbr :title="t('dashboard.mark_notification_as_unread')">
                    <Icon name="fa6-solid:envelope-circle-check" class="text-slate-500 text-base p-1" />
                  </abbr>
                </button>
                <button v-else class="default-xs h-6 w-6 rounded full hover:bg-slate-200"
                  @click="markNotification(result)">
                  <abbr :title="t('dashboard.mark_notification_as_read')">
                    <Icon name="fa6-solid:envelope-open" class="text-slate-500 text-base p-1" />
                  </abbr>
                </button>
                <button v-if="!result.archived_by.map(user => user.username).includes(username)" class="default-xs h-6 w-6 rounded full hover:bg-slate-200"
                  @click="activateNotification(result)">
                  <abbr :title="t('dashboard.archive_notification')">
                    <Icon name="fa6-solid:box-archive" class="text-slate-500 text-base p-1" />
                  </abbr>
                </button>
                <button v-else class="default-xs h-6 w-6 rounded full hover:bg-slate-200"
                  @click="activateNotification(result)">
                  <abbr :title="t('dashboard.unarchive_notification')">
                    <Icon name="fa6-solid:box-open" class="text-slate-500 text-base p-1" />
                  </abbr>
                </button>
              </div>
            </div>
            <hr class="opacity-50" />
          </li>
          <hr />
          <li v-if="loadingMore" class="text-center py-4">
            <AppLoading :text="$t('common.loading')" />
          </li>
          <li v-if="allDataLoaded && data?.length > 0" class="text-center text-sm py-4 text-gray-500">
            {{ $t('common.all_data_loaded') }}
          </li>
        </ul>
      </div>
      <div v-else class="mx-auto text-center mt-2 flex items-center justify-center">
        <div class="text-slate-400 text-sm text-center mx-auto">
          <p class="flex items-center gap-2">
            {{ t('common.no_records') }}
            <Icon name="fa6-solid:circle-exclamation" class="text-[12px]" />
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

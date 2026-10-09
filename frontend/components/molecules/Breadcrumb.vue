<script setup>
import { useRoute } from 'vue-router'
import { useSidebarStore } from '~/stores/useNavSideBar';

const sidebarStore = useSidebarStore();
const route = useRoute()
const { $NotificationApiService, $GeneralNoteApiService, $DailyDocumentApiService } = useNuxtApp();
const { t, te } = useI18n();
const crumbs = ref([]);

// Format a route segment to be human-readable
const formatSegment = (segment) => {
  // Remove leading/trailing slashes and split by hyphens
  const cleaned = segment.replace(/^\/+|\/+$/g, '');
  if (!cleaned) return '';
  
  // Split by hyphens and capitalize each word
  return cleaned
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

// Get translation key for a segment, trying multiple variations
const getTranslationKey = (segment) => {
  const cleaned = segment.replace(/^\/+|\/+$/g, '');
  if (!cleaned) return null;
  
  // Special handling for common actions
  if (cleaned.toLowerCase() === 'add') {
    try {
      return t('common.add');
    } catch (e) {
      // Fall through to default formatting
    }
  }
  
  if (cleaned.toLowerCase() === 'edit') {
    try {
      return t('common.edit');
    } catch (e) {
      // Fall through to default formatting
    }
  }
  
  // Try different translation key formats
  const variations = [
    cleaned.replace(/-/g, '_'), // contract-requests -> contract_requests
    cleaned, // contract-requests -> contract-requests
    cleaned.replace(/-/g, ''), // contract-requests -> contractrequests
  ];
  
  // First, try regular translations
  for (const key of variations) {
    try {
      const translation = te(key) ? t(key) : null;
      // If translation exists and is different from the key, use it
      if (translation && translation !== key) {
        return translation;
      }
    } catch (e) {
      // Translation not found, try next variation
    }
  }
  
  // If no regular translation found, try breadcrumb translations
  for (const key of variations) {
    try {
      const breadcrumbKey = `breadcrumb.${key}`;
      const translation = te(breadcrumbKey) ? t(breadcrumbKey) : null;
      // If translation exists and is different from the key, use it
      if (translation && translation !== breadcrumbKey) {
        return translation;
      }
    } catch (e) {
      // Translation not found, try next variation
    }
  }
  
  return null;
};

// Get display text for a segment
const getSegmentText = (segment) => {
  // Try to get translation first
  const translation = getTranslationKey(segment);
  if (translation) {
    return translation;
  }
  
  // Fall back to formatted segment
  return formatSegment(segment);
};

const fillCrumbs = () => {
  crumbs.value = []
  
  // Parse the path into segments
  const pathSegments = route.path.split('/').filter(segment => segment.length > 0);
  
  // Build breadcrumb items from path segments
  let currentPath = '';
  for (let i = 0; i < pathSegments.length; i++) {
    const segment = pathSegments[i];
    currentPath += '/' + segment;
    
    // Check if this segment should not be clickable (edit needs an ID after it)
    const isEditSegment = segment.toLowerCase() === 'edit';
    const isNotClickable = isEditSegment || i === 0 || i === pathSegments.length - 1;
    
    crumbs.value.push({
      text: getSegmentText(segment),
      link: currentPath,
      isClickable: !isNotClickable
    });
  }
};

fillCrumbs();

watch(() => route.path, async () => {
  fillCrumbs();
  let newNotifications = await $NotificationApiService.checkNewNotifications();
  sidebarStore.newNotificationsFound(newNotifications);
  let newDailyDocuments = await $DailyDocumentApiService.checkNewDailyDocuments();
  sidebarStore.newDailyDocumentsFound(newDailyDocuments);
});

let authToken = '';

if (process.client) {
  authToken = localStorage.getItem('auth_token') || '';
}

onMounted(async () => {
  if (authToken != '') {
    let newNotifications = await $NotificationApiService.checkNewNotifications();
    sidebarStore.newNotificationsFound(newNotifications);
    let newDailyDocuments = await $DailyDocumentApiService.checkNewDailyDocuments();
    sidebarStore.newDailyDocumentsFound(newDailyDocuments);
  }
});

</script>

<template>
  <nav aria-label="Breadcrumb">
    <ol class="flex gap-2 align-center items-center ">
      <button v-if="!sidebarStore.isOpen"
        class="flex gap-3 opacity-50 items-center border rounded px-2 py-1 text-slate-600 hover:opacity-100 hover:border-slate-400 active:bg-slate-300"
        @click="sidebarStore.openSidebar">
        <Icon name="fa6-solid:angles-right" class="text-slate-400" />
      </button>
      <li>
        <NuxtLink to="/">
          <Icon name="fa6-solid:house" class="text-slate-500" />
        </NuxtLink>
      </li>
      <template v-for="(crumb, index) in crumbs" :key="index">
        <li role="separator" class="text-slate-400">/</li>
        <li>
          <NuxtLink 
            v-if="crumb.isClickable" 
            :to="crumb.link"
            class="text-slate-600 hover:text-slate-800 hover:underline">
            {{ crumb.text }}
          </NuxtLink>
          <span v-else class="text-slate-800 font-medium">
            {{ crumb.text }}
          </span>
        </li>
      </template>
      <!-- <li>
        <AtomsLanguageSwitcher />
      </li> -->
    </ol>
  </nav>
</template>

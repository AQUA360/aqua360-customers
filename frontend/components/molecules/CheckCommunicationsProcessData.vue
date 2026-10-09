<script setup>
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import CommunicationRegion from '../organisms/CommunicationRegion.vue';
import { formatDate } from '~/utils/date';
import FieldDetail from '../atoms/FieldDetail.vue';

const { t } = useI18n();

const props = defineProps({
  communicationIds: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['excluded-communications']);

const saving = ref(false);
const communications = ref([]);
const excludedCommunicationIds = ref(new Set());

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const isSubRegionOpen = ref(false);
const selectedCommunicationId = ref(null);

const syncCommunications = () => {
  const list = (props.communicationIds || []).map((communication) => ({ ...communication }));
  communications.value = list;
  excludedCommunicationIds.value = new Set(
    list.filter((communication) => communication.is_excluded).map((communication) => communication.id),
  );
};

const visibleCommunications = computed(() => {
  return communications.value.map((communication) => ({
    ...communication,
    is_excluded: excludedCommunicationIds.value.has(communication.id),
  }));
});

const excludedCount = computed(() => excludedCommunicationIds.value.size);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  if (component === 'CommunicationRegion') {
    selectedCommunicationId.value = id;
  }
};

const closeSubRegion = () => {
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  isSubRegionOpen.value = false;
  selectedCommunicationId.value = null;
};

const toggleExcluded = (communication) => {
  if (excludedCommunicationIds.value.has(communication.id)) {
    excludedCommunicationIds.value.delete(communication.id);
    return;
  }
  excludedCommunicationIds.value.add(communication.id);
  emit('excluded-communications', excludedCommunicationIds.value);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const save = () => {
  saving.value = true;

  try {
    const payload = {
      comm_ids: communications.value
        .map((communication) => communication.id)
        .filter((id) => !excludedCommunicationIds.value.includes(id)),
    };
    console.log('payload');
    console.log(payload);
  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
};

watch(
  () => props.communicationIds,
  () => {
    syncCommunications();
  },
  { immediate: true },
);

</script>

<template>
  <div class="h-full flex flex-col min-w-0">

    <!-- <div class="flex items-center justify-between mb-2 px-1">
      <span class="text-slate-500">
        {{ $t('common.total') }}: {{ visibleCommunications.length }}
      </span>
      <span class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1">
        {{ excludedCount }} {{ $t('billing_block.excluded_multiple') }}
      </span>
    </div> -->

    <div class="rounded bg-white overflow-auto" :style="{
      minHeight: 'calc(100vh - 300px)',
      maxHeight: 'calc(100vh - 300px)',
    }">
      <ul v-if="visibleCommunications.length" class="py-1 space-y-2">
        <li
          v-for="communication in visibleCommunications"
          :key="communication.id"
          class="group relative overflow-hidden rounded-lg border transition-all duration-150 hover:bg-sky-50/80 hover:border-sky-300"
          :class="{
            'bg-red-50/90 border-red-200/90': communication.is_excluded,
            'border-slate-200/80': !communication.is_excluded,
            'bg-yellow-50 border-yellow-200/80': selectedCommunicationId === communication.id,
          }"
        >
          <button
            type="button"
            class="w-full text-left px-4 py-3 flex items-center justify-between gap-3"
            @click="showDetail('CommunicationRegion', communication.id)"
          >
            <div class="flex flex-col h-full" :class="{ 'opacity-50': communication.is_excluded }">
              <div class="min-w-0 flex gap-2 h-full items-start">
                <span class="text-sm font-semibold text-slate-700 truncate">
                  {{ communication.token }}
                </span>
                <AtomsColorBadge :color="communication.status_color" :value="communication.status_name" />
              </div>
              <div class="flex flex-wrap gap-x-3 text-[11px] text-slate-500 h-full mt-0">
                <FieldDetail :label="$t('user')" :value="communication.user_username || t('common.admin')" />
                <FieldDetail :label="$t('common.creation_date')" :value="formatDate(communication.created_at)" />
                <FieldDetail :label="$t('common.send_date')" :value="formatDate(communication.due_date)" />
              </div>
            </div>
            <div class="grid grid-cols-[1fr,100px] gap-x-2">
              <div :class="{ 'opacity-50': communication.is_excluded }">
                <p class="text-sm text-slate-600 truncate mt-0.5 text-right">
                  {{ communication.person_token }} · {{ communication.person_name }}
                </p>
                <div class="mt-2 flex flex-col justify-start text-right text-[11px] text-slate-500">
                  <p class="text-sky-700 font-semibold">{{ communication.type_names || '—' }}</p>
                  <p v-if="communication.used_email" class="text-sky-700 font-semibold">{{ communication.used_email }}</p>
                </div>
              </div>

              <div class="flex justify-end items-center">
                <button
                  class="px-2 py-1 h-fit flex items-center text-amber-700 bg-amber-50 border border-amber-200 rounded shadow-sm hover:bg-amber-100 gap-x-2"
                  @click.stop="toggleExcluded(communication)"
                >
                  <Icon :name="communication.is_excluded ? 'fa6-solid:arrow-up-from-bracket' : 'fa6-solid:ban'" class="text-xs" />
                  <span class="text-sm">
                    {{ communication.is_excluded ? $t('billing_block.include') : $t('billing_block.exclude') }}
                  </span>
                </button>
              </div>
            </div>
          </button>

          <button
            type="button"
            class="w-48 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-sky-200/50 to-transparent h-full absolute top-0 left-0 flex items-center justify-start z-10 px-5"
            @click="showDetail('CommunicationRegion', communication.id)"
          >
            <Icon name="fa6-solid:eye" class="w-5 h-5 text-sky-500" />
          </button>
        </li>
      </ul>
      <div v-else class="py-8 px-3 text-center text-sm text-slate-500">
        {{ t('common.no_data_found') }}
      </div>
    </div>

    
  </div>

  <div
    id="right_page"
    role="region"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden"
    :class="{
      'translate-x-0': showRegionDetailComponent,
      'translate-x-[2000px]': !showRegionDetailComponent,
      'w-[95%]': isSubRegionOpen,
      'w-[55%]': !isSubRegionOpen,
    }"
  >
    <div id="region_nav" class="mb-3 px-3">
      <button class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300" @click="closeSubRegion()">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <CommunicationRegion
        v-if="showRegionDetailComponent == 'CommunicationRegion'"
        :id="parseInt(regionDetailId)"
        :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent"
      />
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';

const props = defineProps({
  item: Object,
  person: Object,
  onlyEmail: {
    type: Boolean,
    default: false
  },
  onlyPhone: {
    type: Boolean,
    default: false
  },
  showPersonName: {
    type: Boolean,
    default: true
  },
  allowClick: {
    type: Boolean,
    default: true
  },
  isSMS: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['add-call']);
</script>

<template>
  <div v-if="onlyEmail">
    <span v-if="person && showPersonName">{{ person.full_name }} &gt;{{ item.email }}&lt;</span>
    <span v-else>{{ item.email }}</span>
  </div>
  <div v-else-if="onlyPhone">
    <span v-if="person && showPersonName">{{ person.full_name }}: {{ item.phone }}</span>
    <span v-else>{{ item.phone }}</span> <em v-if="item.role">({{ item.role }})</em>
  </div>
  <div v-else>
    <slot>
      <p v-if="person && showPersonName" class="mb-2 font-semibold">{{ person.full_name }}</p>
      <AtomsFieldDetail v-if="item.email" :label="$t('common.email_long')" :icon="'fa6-solid:at'" >
        <a v-if="item.email && allowClick" :href="'mailto:' + item.email" class="text-sky-500 underline hover:no-underline truncate">{{ item.email }}</a>
        <span v-else-if="item.email && !allowClick" class="text-slate-800 truncate">{{ item.email }}</span>
        <!-- <span v-else class="truncate">
          {{ $t('common.no_email_long') }}
        </span> -->
      </AtomsFieldDetail>
      <AtomsFieldDetail :label="$t('common.tlf')" :icon="'fa6-solid:phone'" >
        <div class="flex items-center gap-1">
          <Icon v-if="isSMS" name="fa6-solid:comment-sms" class="mb-1 text-slate-400" />
          <button v-if="item.phone && allowClick" @click="() => emit('add-call', item)"
          class="text-sky-500 underline hover:no-underline text-left">{{ item.phone }}</button>
          <span v-else-if="item.phone && !allowClick" class="text-slate-800">{{ item.phone }}</span>
          <span v-else class="truncate">
            {{ $t('common.no_tlf') }}
          </span>
        </div>
      </AtomsFieldDetail>
      <div v-if="item.role">{{ item.role }}</div>
    </slot>
  </div>
</template>
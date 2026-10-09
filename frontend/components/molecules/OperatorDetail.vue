<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';

const { $AddressHelper } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object
});

const emit = defineEmits(['show-detail', 'clickChangeStatus']);

const showDetail = function (component, id) {
  emit('show-detail', { component: component, id: id })
}
</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.code")' :value=data.token />
    <FieldDetail :label='$t("common.type")'>
      <div class="flex items-center gap-2">
        <Icon v-if="data.is_team" name="fa6-solid:users" class="text-blue-500" />
        <Icon v-else name="fa6-solid:user" class="text-slate-400" />
        <span>{{ data.is_team ? $t('common.team') : $t('common.operator') }}</span>
      </div>
    </FieldDetail>
  </div>

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.name")' :value=data.name />
    <FieldDetail :label='$t("common.surname")' :value=data.surname />
  </div>
  
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.tlf")' :value=data.phone>
      <a :href="'tel:' + data.phone" class="text-sky-500 underline hover:no-underline">{{ data.phone }}</a>
    </FieldDetail>
    <FieldDetail :label='$t("common.email")' :value=data.email>
      <a :href="'mailto:' + data.email" class="text-sky-500 underline hover:no-underline">{{ data.email }}</a>
    </FieldDetail>
  </div>

  <!-- Team members section -->
  <div v-if="data.is_team && data.description && Array.isArray(data.description) && data.description.length > 0" class="mt-4">
    <div class="border border-gray-300 rounded-lg p-4 bg-slate-50">
      <h3 class="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
        <Icon name="fa6-solid:users" class="text-blue-500" />
        {{ $t('common.team_members') }}
      </h3>
      <div class="space-y-2">
        <div v-for="member in data.description" :key="member.id" class="bg-white border border-gray-200 rounded p-3">
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span class="text-slate-500">{{ $t('common.username') }}:</span>
              <span class="ml-2 font-medium">{{ member.username }}</span>
            </div>
            <div>
              <span class="text-slate-500">{{ $t('common.name') }}:</span>
              <span class="ml-2 font-medium">{{ member.name }}</span>
            </div>
            <div v-if="member.email" class="col-span-2">
              <span class="text-slate-500">{{ $t('common.email') }}:</span>
              <a :href="'mailto:' + member.email" class="ml-2 text-sky-500 underline hover:no-underline">{{ member.email }}</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

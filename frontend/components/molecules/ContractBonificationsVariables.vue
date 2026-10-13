<script setup>
import { formatDate } from '~/utils/date';
import VariableDetail from '~/components/molecules/VariableDetail.vue';

const { t } = useI18n();

const props = defineProps({
  contract: Object,
  // Logger entries ("contract-expired-bonifications-variables"), each with expired_variable and/or expired_bonification
  expired_variables: Array,
  expired_bonifications: Array,
  canChange: Boolean
});

const emit = defineEmits(['edit-variable']);

// A bonification is a grouping of variables: attach every contract variable to its bonification,
// so the edit pencil works on the same objects the old variables tab used.
const activeGroups = computed(() => {
  const variables = props.contract?.variables || [];
  return (props.contract?.bonifications || []).map(bonification => {
    const byId = new Map((bonification.variables || []).map(v => [v.id, v]));
    variables.filter(v => v.bonification === bonification.id).forEach(v => byId.set(v.id, v));
    return { bonification, variables: [...byId.values()] };
  });
});

const standaloneVariables = computed(() => {
  const bonificationIds = new Set((props.contract?.bonifications || []).map(b => b.id));
  const grouped = new Set(activeGroups.value.flatMap(g => g.variables.map(v => v.id)));
  return (props.contract?.variables || []).filter(v => !grouped.has(v.id) && !bonificationIds.has(v.bonification));
});

// The log has one entry per expired variable, so the same bonification can appear several times.
const expiredGroups = computed(() => {
  const entries = new Map();
  [...(props.expired_variables || []), ...(props.expired_bonifications || [])].forEach(e => entries.set(e.id, e));
  const groups = new Map();
  const standalone = new Map();
  for (const entry of entries.values()) {
    const bonification = entry.expired_bonification;
    const variable = entry.expired_variable;
    if (bonification) {
      if (!groups.has(bonification.id)) groups.set(bonification.id, { bonification, variables: new Map() });
      if (variable) groups.get(bonification.id).variables.set(variable.id, variable);
    } else if (variable) {
      standalone.set(variable.id, variable);
    }
  }
  return {
    groups: [...groups.values()].map(g => ({
      bonification: g.bonification,
      variables: g.variables.size ? [...g.variables.values()] : (g.bonification.variables || [])
    })),
    variables: [...standalone.values()]
  };
});

const hasActive = computed(() => activeGroups.value.length > 0 || standaloneVariables.value.length > 0);
const hasExpired = computed(() => expiredGroups.value.groups.length > 0 || expiredGroups.value.variables.length > 0);

const bonificationPeriod = (b) => {
  if (!b.start_at && !b.end_at) return '';
  return [b.start_at ? `${t('common.from')} ${formatDate(b.start_at)}` : '', b.end_at ? `${t('common.to')} ${formatDate(b.end_at)}` : '']
    .filter(Boolean).join(' ');
};
</script>

<template>
  <div>
    <div v-if="!hasActive && !hasExpired" class="footering text-slate-500 p-2">{{ t('common.no_records') }}</div>

    <div v-for="group in activeGroups" :key="group.bonification.id" class="mb-3 rounded border border-sky-200 bg-sky-50 p-3">
      <div class="flex flex-wrap items-center gap-2 mb-2">
        <Icon name="fa6-solid:percent" class="text-sky-600" />
        <span class="font-semibold">{{ group.bonification.bonification_type?.name || t('contract_block.no_bonification_type') }}</span>
        <span v-if="group.bonification.is_aca_bonification" class="text-xs px-3 py-1 rounded-full whitespace-nowrap"
          :class="group.bonification.sent_to_aca ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'">
          {{ group.bonification.sent_to_aca ? t('common.sent_to_aca') : t('common.pending_to_send_aca') }}
        </span>
        <span v-if="bonificationPeriod(group.bonification)" class="text-sm text-slate-500">
          {{ bonificationPeriod(group.bonification) }}
        </span>
      </div>
      <ul v-if="group.bonification.documentation_files?.length" class="mb-2 text-sm">
        <li v-for="document in group.bonification.documentation_files" :key="document.id">
          <Icon name="fa6-solid:check" class="mr-2" />
          <a v-if="document.file" :href="document.file" target="_blank" class="text-blue-500 underline">{{ document.name }}</a>
          <span v-else>{{ document.name }}</span>
        </li>
      </ul>
      <div v-if="group.variables.length" class="grid grid-cols-2 gap-x-3 border-t border-sky-200 pt-2">
        <VariableDetail v-for="v in group.variables" :key="v.id" :item="v" :deleteButton="false" :editButton="canChange"
          @edit="emit('edit-variable', v)" />
      </div>
    </div>

    <div v-if="standaloneVariables.length" class="mb-3 rounded border border-slate-200 p-3">
      <div class="flex items-center gap-2 mb-2">
        <Icon name="fa6-solid:shuffle" class="text-slate-500" />
        <span class="font-semibold">{{ t('contract_block.variables_without_bonification') }}</span>
      </div>
      <div class="grid grid-cols-2 gap-x-3">
        <VariableDetail v-for="v in standaloneVariables" :key="v.id" :item="v" :deleteButton="false" :editButton="canChange"
          @edit="emit('edit-variable', v)" />
      </div>
    </div>

    <template v-if="hasExpired">
      <span class="inline-block mt-8 mb-3 text-slate-500 text-sm bg-slate-100 rounded-md px-2 py-1">
        {{ t('contract_block.expired_bonifications_variables') }}
      </span>

      <div v-for="group in expiredGroups.groups" :key="group.bonification.id" class="mb-3 rounded border border-slate-200 bg-slate-100 p-3">
        <div class="flex items-center gap-2 mb-2">
          <Icon name="fa6-solid:percent" class="text-slate-400" />
          <span class="font-semibold text-slate-500 line-through italic">
            {{ group.bonification.bonification_type?.name || t('contract_block.no_bonification_type') }}
          </span>
        </div>
        <div v-if="group.variables.length" class="grid grid-cols-2 gap-x-3 border-t border-slate-200 pt-2">
          <VariableDetail v-for="v in group.variables" :key="v.id" :item="v" :deleteButton="false" :is_expired="true" />
        </div>
      </div>

      <div v-if="expiredGroups.variables.length" class="mb-3 rounded border border-slate-200 bg-slate-100 p-3">
        <div class="flex items-center gap-2 mb-2">
          <Icon name="fa6-solid:shuffle" class="text-slate-400" />
          <span class="font-semibold text-slate-500">{{ t('contract_block.variables_without_bonification') }}</span>
        </div>
        <div class="grid grid-cols-2 gap-x-3">
          <VariableDetail v-for="v in expiredGroups.variables" :key="v.id" :item="v" :deleteButton="false" :is_expired="true" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import ClauseDetail from '~/components/molecules/ClauseDetail.vue';

const props = defineProps({
  contract: Object,
});

const emit = defineEmits(['change']);

const { t } = useI18n();
const { $ContractClausesApiService, $ClauseTemplateApiService } = useNuxtApp();

const clauses = ref([...(props.contract?.clauses || [])]);
const templates = ref([]);
const loading = ref(true);
const saving = ref(false);

// Templates already assigned are not offered again.
const availableTemplates = computed(() => {
  const used = new Set(clauses.value.map((c) => c.template).filter(Boolean));
  return templates.value.filter((tpl) => !used.has(tpl.id));
});

const getData = async () => {
  loading.value = true;
  const [templatesResponse, clausesResponse] = await Promise.all([
    $ClauseTemplateApiService.getAll('', { is_active: true }),
    $ContractClausesApiService.getAll('', { contract: props.contract.id }),
  ]);
  templates.value = templatesResponse.results;
  clauses.value = clausesResponse.results;
  loading.value = false;
};

onMounted(() => {
  getData();
});

const addClause = async (template) => {
  if (saving.value) return;
  saving.value = true;
  try {
    const saved = await $ContractClausesApiService.save({
      token: template.token,
      title: template.title,
      clause: template.clause,
      template: template.id,
      contract: props.contract.id,
    });
    clauses.value.push(saved);
    emit('change');
  } finally {
    saving.value = false;
  }
};

const removeClause = async (clause) => {
  if (saving.value) return;
  if (!confirm(t('contract_block.confirm_remove_clause'))) return;
  saving.value = true;
  try {
    if (clause.contract_request) {
      // Keep the clause on the original request, only detach it from the contract.
      await $ContractClausesApiService.save({ id: clause.id, contract: null });
    } else {
      await $ContractClausesApiService.doDelete(clause);
    }
    clauses.value = clauses.value.filter((item) => item.id !== clause.id);
    emit('change');
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.modify') }} {{ $t('contract_block.clauses') }}</H1>
    </div>

    <p class="text-sm text-slate-500 mb-4">
      {{ $t('contract_block.contract_clauses_regenerate_notice') }}
    </p>

    <h2 class="font-semibold text-slate-700 mb-2">{{ $t('contract_block.clauses') }}</h2>
    <ul class="mb-6">
      <li v-for="clause in clauses" :key="clause.id"
        class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 mb-2">
        <ClauseDetail :item="clause" />
        <button :disabled="saving" @click="removeClause(clause)" class="text-slate-500 ml-2"
          :aria-label="$t('common.delete')">
          <Icon name="fa6-solid:trash" />
        </button>
      </li>
      <li v-if="!loading && clauses.length === 0" class="text-slate-500">
        {{ $t('contract_block.no_clauses') }}
      </li>
    </ul>

    <h2 class="font-semibold text-slate-700 mb-2">{{ $t('contract_block.clause_selection') }}</h2>
    <div class="item__list">
      <button v-for="item in availableTemplates" :key="item.id" :disabled="saving"
        class="item__list__item flex gap-2 border mb-2 w-full py-1 px-3" @click="addClause(item)">
        <Icon name="fa-solid:plus" class="text-slate-500 mt-1" />
        <ClauseDetail :item="item" />
      </button>
    </div>
    <p v-if="!loading && availableTemplates.length === 0" class="text-slate-500">
      {{ $t('contract_block.no_clauses_configured') }}
    </p>
  </div>
</template>

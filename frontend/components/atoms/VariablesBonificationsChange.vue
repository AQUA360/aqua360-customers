<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n()
const props = defineProps({
  id: Number,
  object: Object
});

const emit = defineEmits(['delete', 'update:count']);

const { $LoggerApiService } = useNuxtApp();

const pending = ref(true);
const change = ref('')


const getData = async () => {
  pending.value = true;
  try {
    const result = await $LoggerApiService.getAll("contract-bonifications-variables-change", props.id);
    change.value = result.results
    emit('update:count', change.value.length)
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false;
  }
}


onMounted(() => {
  getData()
})

</script>
<template>
  <div v-if="change && change.length > 0">
    <article v-for="change in change" 
      class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
      <span class="absolute left-[-5px] top-0 text-[10px]">
        <Icon name="fa6-solid:circle" class="text-sky-500" />
      </span>
      <footer class="flex justify-between items-center pt-1">
        <div class="flex items-center mb-1">
          <p v-if="change.user" class="text-sm text-gray-700 mr-3">{{ change.user?.username }}</p>
          <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
          <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
            <TimeRelative :datetime=change.timestamp></TimeRelative>
          </p>
        </div>
        
      </footer>

      <div>
        
        <div  v-if="change.previous_bonification !== change.current_bonification" >

          <p class="text-slate-500 italic text-xs">{{ t("contract_block.bonification") }}</p>
          <p class="text-sm flex gap-3">
            <span class="text-slate-500">{{ change.previous_bonification? change.previous_bonification.bonification_type.name:  t("contract_block.added_bonification") }}</span>
            <span>&rarr;</span>
            <span class="text-slate-900">{{ change.current_bonification? change.current_bonification.bonification_type.name: t("contract_block.deleted_bonification") }}</span>
          </p>
        </div>

        <div v-if="change.previous_variable !== change.current_variable">
          <p class="text-slate-500 italic text-xs">{{ t("pricing_block.variable") }}</p>
          <p class="text-sm flex gap-3">
            <span class="text-slate-500">{{ change.previous_variable? change.previous_variable.name : t("contract_block.added_variable") }}</span>
            <span>&rarr;</span>
            <span class="text-slate-900">{{ change.current_variable? change.current_variable.name : t("contract_block.deleted_variable") }}</span>
          </p>
        </div>

      </div>

    </article>
  </div>
  <div v-else>
    <div class="footering text-slate-500 p-2">
      {{ t('common.no_changes') }}
    </div>
  </div>
  
</template>
<script setup>
import TimeRelative from '../atoms/TimeRelative.vue';
import AtomsIBAN from '../atoms/IBAN.vue';
const props = defineProps({
  id: Number,
  reload: Boolean
});

const pending = ref(true);
const error = ref(null);
const data = ref(null);

const items = ref([]);

const { $LoggerApiService } = useNuxtApp();
const emit = defineEmits(['update:count']);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $LoggerApiService.getAll('invoice-data', props.id);
    items.value = data.results;
    console.log("items.value invoice data log");
    console.log(items.value);
    emit('update:count', items.value.length);
  } catch (err) {
    console.log(err);
  } finally {
    pending.value = false;
  }
};

watch(() => props.reload, async () => {
  await getData();
});

onMounted(async () => {
  await getData();
});

</script>

<template>
  <div v-if="items.length > 0" class="border-l ml-4 mt-4">
    <div v-for="item in items" :key="item.id">
      <article
        class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
        <span class="absolute left-[-5px] top-0 text-[10px]">
          <Icon name="fa6-solid:circle" class="text-sky-500" />
        </span>
        <footer class="flex justify-between items-center pt-1">
          <div class="flex items-center mb-1">
            <p v-if="item.user" class="text-sm text-gray-700 mr-3">{{ item.user?.username }}</p>
            <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
            <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
              <TimeRelative :datetime=item.timestamp></TimeRelative>
            </p>
          </div>
          <div>
            <span class="text-slate-400 text-sm">{{ formatDateTime(item.timestamp) }}</span>
          </div>
        </footer>
        <p v-if="item.previous_address && item.current_address" class="text-sm flex gap-3">
          <span class="text-slate-400">
            {{ item.previous_address }}
          </span>
          &rarr;
          <span class="text-slate-900 font-medium">
            {{ item.current_address }}
          </span>
        </p>
        <p v-if="item.previous_payment_type && item.current_payment_type" class="text-sm flex gap-3">
          <span class="text-slate-400">
            {{ item.previous_payment_type }}
          </span>
          &rarr;
          <span class="text-slate-900 font-medium">
            {{ item.current_payment_type }}
          </span>
        </p>
        <p v-if="item.previous_iban || item.current_iban" class="text-sm flex gap-3 items-center mt-1">
          <span v-if="item.previous_iban">
            <AtomsIBAN :value="item.previous_iban" />
          </span>
          <span v-else class="text-slate-400">-</span>
          <span class="text-slate-400">&rarr;</span>
          <span v-if="item.current_iban">
            <AtomsIBAN :value="item.current_iban" />
          </span>
          <span v-else class="text-slate-400">-</span>
        </p>
      </article>
    </div>
  </div>
  <div v-else class="mt-2">
    <div class="">
      <span class="footering text-sm text-slate-500">{{ $t('common.no_data_found') }}</span>
    </div>
  </div>
</template>

<script setup>

const { $BillingApiService } = useNuxtApp();

const badges = ref([]);

const getData = async () => {
  const data = await $BillingApiService.getBadges();
  badges.value = data;
}

onMounted(() => {
  getData()
})

const refresh = () => {
  getData()
}

defineExpose({ refresh })
</script>


<template>
  <div>
    <div class="flex justify-center items-center gap-2">
      <div class="rounded-full bg-slate-200 px-2 py-1" v-for="b in badges">
        <span>{{ b.token }}: </span>
        <span class="font-bold">{{ b.total }}</span>
      </div>
    </div>
  </div>
</template>
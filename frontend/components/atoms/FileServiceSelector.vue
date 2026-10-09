<script setup>
import { ref } from 'vue';
import { Services, ServicesIcons } from '~/utils/document-manager';

const props = defineProps({
  isVisible: Boolean,
  onClose: Function,
  onSelect: Function,
});

const services = ref([])

const selectService = (service) => {
  props.onSelect(service);
  props.onClose();
};

const getServices = () => {
  services.value = Object.keys(Services).map(key => {
    return {
      value: key,
      label: Services[key],
      icon: ServicesIcons[key]
    }
  })
}


onMounted(() => {
  getServices()
})

const closeModal = () => {
  props.onClose();
};
</script>

<template>
  <div v-if="isVisible" @click="closeModal"
    class="fixed inset-0 bg-black bg-opacity-10 flex justify-center items-center z-50">
    <div @click.stop class="bg-white rounded-lg shadow-2xl p-6 text-center">
      <h2 class="text-xl font-semibold mb-4">{{ $t('common.select_service') }}</h2>
      <div class="mb-4">
        <button v-for="service in services" :key="service.value" @click="selectService(service)"
          class="w-full mb-2 px-4 py-2 border border-sky-500 text-sky-500 rounded-md transition-colors duration-300 hover:bg-sky-500 hover:text-white">
          <Icon :name="service.icon" class=" mr-2" />
          {{ service.label }}
        </button>
      </div>
      <button class="button-default" @click="closeModal">
        {{ $t('common.cancel') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
/* You can add any additional custom styles here if needed */
</style>

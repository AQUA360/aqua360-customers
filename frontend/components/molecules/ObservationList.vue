<script setup>
import { ref, watch, onMounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

const { $ObservationApiService, $OperatorApiService } = useNuxtApp();
const { t } = useI18n();
// Define an object for your plugin
const props = defineProps({
  module: String,
  id: Number,
  parent_entity: String,
  url_entity: String,
  allow_mark: Boolean,
  reload: Boolean
});

const pending = ref(true);
const error = ref(null);
const data = ref(null);

const observations = ref([]);
const operatorCache = ref({});

const emit = defineEmits(['update:observation-count', 'update:important-observations']);

const getData = async (load = true) => {
  pending.value = load;
  error.value = null;
  try {
    const result = await $ObservationApiService.getObservations('' + props.id, props.module, props.parent_entity, props.url_entity || props.parent_entity);
    data.value = result;
    await loadObservations(result);
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
};
getData();

const loadObservations = async (data) => {
  observations.value = [];
  const results = [...data.results];
  
  for (const element of results) {
    let userName = '';
    if (element.user) {
      userName = element.user.first_name + ' ' + element.user.last_name;
    } else if (element.operator) {
      const operatorId = element.operator;
      if (!operatorCache.value[operatorId]) {
        try {
          const opDetail = await $OperatorApiService.getDetail(operatorId);
          operatorCache.value[operatorId] = opDetail.name + ' ' + opDetail.surname;
        } catch (e) {
          console.error('Error fetching operator detail:', e);
          operatorCache.value[operatorId] = t('common.operator') + ' #' + operatorId;
        }
      }
      userName = operatorCache.value[operatorId];
    } else {
      userName = t('common.admin');
    }

    let observation = {
      id: element.id,
      user: userName,
      date: element.created_at,
      observation: element.observation,
      status_name: element.status_name,
      is_important: element.is_important
    }
    observations.value.push(observation);
  }



  emit('update:observation-count', observations.value.length);
};

const deleteObservation = async (item_id) => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    try {
      await $ObservationApiService.deleteObservation(item_id, props.module, props.url_entity || props.parent_entity);

      const index = observations.value.findIndex(item => item.id === item_id);
      if (index !== -1) {
        observations.value.splice(index, 1);
      }

      emit('update:observation-count', observations.value.length);
    } catch (err) {
      console.error(err);
    }
  }
};

const markObservation = async (item) => {
  try {
    let data = {
      id: item.id,
      is_important: !item.is_important
    };

    data[props.parent_entity] = props.id;

    const res = await $ObservationApiService.updateObservation(data, props.module, props.url_entity || props.parent_entity);
    await getData(false);
    emit('update:important-observations');
  } catch (err) {
    console.error(err);
  }
}

const addObservation = async (observation) => {
  if (!observation?.trim()) {
    return;
  }
  try {
    let data = {
      observation: observation
    };

    data[props.parent_entity] = props.id;

    const res = await $ObservationApiService.postObservation(data, props.module, props.url_entity || props.parent_entity);

    let userName = '';
    if (res.user) {
      userName = res.user.first_name + ' ' + res.user.last_name;
    } else if (res.operator) {
      const operatorId = res.operator;
      if (!operatorCache.value[operatorId]) {
        try {
          const opDetail = await $OperatorApiService.getDetail(operatorId);
          operatorCache.value[operatorId] = opDetail.name + ' ' + opDetail.surname;
        } catch (e) {
          operatorCache.value[operatorId] = t('common.operator') + ' #' + operatorId;
        }
      }
      userName = operatorCache.value[operatorId];
    } else {
      userName = t('common.admin');
    }

    let new_observation = {
      id: res.id,
      user: userName,
      date: res.created_at,
      observation: observation,
      status_name: res.status_name,
    };
    if (props.allow_mark) {
      new_observation.is_important = res.is_important;
    }
    observations.value.unshift(new_observation);

    emit('update:observation-count', observations.value.length);
  } catch (err) {
    console.error(err);
  }
};

watch(() => props.reload, (newValue) => {
  getData();
});

</script>

<template>
  <div class="px-2">
    <AtomsInputTextarea @update:text="addObservation" text="" :autosave="true" :rows="1.25" />
    <MoleculesObservation 
      v-for="observation in observations" 
      @delete:observation="deleteObservation"
      @mark:observation="markObservation"
      :id="observation.id" 
      :object="observation"
      :user="observation.user" 
      :datetime="observation.date" 
      :observation="observation.observation"
      :status_name="observation.status"
      :allow_mark="props.allow_mark">
    </MoleculesObservation>
  </div>
</template>

<style scoped>
.auto-resizing-textarea {
  width: 100%;
  overflow: hidden;
  resize: none;
  box-sizing: border-box;
}

.auto-resizing-textarea:focus-visible {
  outline: none;
}
</style>

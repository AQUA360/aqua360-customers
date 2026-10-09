<script setup>
import { useI18n } from 'vue-i18n';
import { AppColors } from '~/utils/config';

const { t, te } = useI18n();

const isNavigation = ref(true)

const props = defineProps({
  statuses: {
    type: Array,
    required: true
  },
  active: {
    type: Object,
    required: false
  }
});

const isSingle = (status) => { // si l'estat és negatiu: -1, -2, -3, etc. No s'enganxa un amb l'altre, es mostra independent.
  if( typeof status == "undefined" ) {
    return false;
  }

  var token = status?.token;

  if( isNaN(token) ) { // és string, vol dir que està lligada amb el següent estat (no és single)
    return false;
  } else {
    var r = parseInt(token) < 0 ? true : false; // és negatiu, és single
    return r
  }
}

onMounted(() => {
  if( isSingle(props.active) ) {
    isNavigation.value = false
  }
})

// watch active status, si canvia s'ha de mirar si és single o no i establir el mode de navegació
watch(() => props.active, (newVal) => {
  if( isSingle(newVal) ) {
    isNavigation.value = false
  } else {
    isNavigation.value = true
  }
})

const translateStatusName = (name) => {
  if (!name) return '';
  if (name.startsWith('reading_alert_')) {
    return t(`billing_block.${name}`);
  }
  const blockKey = `billing_block.${name}`;
  const resBlock = te(blockKey) ? t(blockKey) : blockKey;
  if (resBlock !== blockKey) return resBlock;
  
  const globalKey = name;
  const resGlobal = te(globalKey) ? t(globalKey) : globalKey;
  if (resGlobal !== globalKey) return resGlobal;

  return name;
};
</script>

<template>
  <ul class="flex" :class="isNavigation ? 'overflow-hidden rounded-lg' : ''">
    <li 
      v-if="isNavigation"
      v-for="(status, index) in statuses" 
      :key="status?.id" 
      class="relative flex items-center cursor-default"
      :class="index == 0 ? 'rounded-l-lg' : ''"
    >
      <span 
        v-if="!isSingle(status)"
        :class="[
          'px-4 py-2 pr-6 border-r border-white-900 bg-blue-500 text-white font-medium shadow-lg clip-right',
          index == 0 ? 'rounded-l-lg' : 'pl-5',
          status.id === active?.id? status?.color ? `badge-${status?.color}` : 'badge-gray': 'badge-gray-light',
        ]"
        :style="{ 'z-index': 9 -index }"
      >
        {{ translateStatusName(status.name) }}
      </span>
    </li>
    <li v-else>
      <span class="px-4 py-2 border-white-900 font-medium rounded-lg"
            :class="`badge-${ active?.color }`">
        {{ translateStatusName(active?.name) }}
      </span>
    </li>
  </ul>
</template>

<style scoped>
.clip-right {
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%);
  margin-right: -10px; /* Adjust spacing for clipping */
}
.clip-right::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 10px;
  background-color: inherit;
  clip-path: polygon(100% 0, 0 50%, 100% 100%);
}

/* No cal cap regla per atenuar la fletxa: `opacity` s'aplica a l'element i a tot
   el que genera, pseudoelements inclosos. N'hi ha prou amb posar la classe
   `opacity-50` al <span>.clip-right i el ::after s'atenua amb ell.
   Aquí hi havia un `.clip-right::after.opacity-50`, que és invàlid (una classe no
   pot anar darrere d'un pseudoelement) i el navegador descartava sencer. */
</style>

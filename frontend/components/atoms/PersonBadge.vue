<script setup>
const props = defineProps({
  person: {
    type: Object,
    required: false
  },
  color: {
    type: String,
    default: null
  },
  // Clicable (p. ex. per obrir la regió de la persona): el pare escolta @click
  clickable: {
    type: Boolean,
    default: false
  }
});

const getName = () => {
  const person = props.person;
  if( ! props.person ) return '';
  if (person.full_name)
    return person.full_name;
  return person.is_juridic ? person.name : `${person.name} ${person.surname}`;
};
</script>


<template>
  <!-- <abbr :title="person?.token" class="inline-block no-underline"><slot>{{ getName() }}</slot></abbr> -->
  <span class="flex justify-between inline-block rounded px-2 py-0.5 text-sm w-full"
  :class="[props.color? 'badge-' + props.color: 'badge-gray', props.clickable ? 'cursor-pointer hover:brightness-95' : 'cursor-default']"
  :role="props.clickable ? 'button' : undefined" :tabindex="props.clickable ? 0 : undefined"
  @keydown.enter="props.clickable && $event.target.click()">
    <slot>
      <span>{{ getName() }}</span>
      <span>{{ person?.token || "" }}</span>
    </slot>
    <!-- Avís d'anomalies vigents (només si les dades de la persona les porten, p. ex. a la regió del contracte) -->
    <AtomsPersonAnomalyBadges v-if="person?.current_anomalies?.length" :anomalies="person.current_anomalies"
      :compact="true" class="shrink-0 ml-2" />
  </span>
</template>
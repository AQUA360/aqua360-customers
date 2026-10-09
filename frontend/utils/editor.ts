// utils/toolbarButtons.ts

export const toolbarButtons = [
  {
    name: 'undo',
    label: 'Desfer',
    description: "Desfer l'últim canvi fet a l'editor",
    icon: 'fa6-solid:rotate-left',
  },
  {
    name: 'redo',
    label: 'Refer',
    description: "Recupera l'últim canvi fet a l'editor",
    icon: 'fa6-solid:rotate-right',
  },
  {
    name: 'image',
    label: 'Imatge',
    description: 'Afegeix una imatge a la plantilla',
    icon: 'fa6-solid:image',
  },
  {
    name: 'break',
    label: 'Espai',
    description: 'Insereix un salt de línia',
    icon: 'fa6-solid:arrows-down-to-line',
  },
  {
    name: 'clearFormat',
    label: 'Desfer format',
    description: 'Elimina tot el format del text seleccionat',
    icon: 'fa6-solid:eraser',
  },
  {
    name: 'format',
    label: 'Format',
    description: 'Escull l\'estil del text (negreta, cursiva, etc.)',
    icon: 'fa6-solid:text-width',
  },
  {
    name: 'headings',
    label: 'Títols',
    description: 'Aplica un estil de títol al text (H1, H2, H3)',
    icon: 'fa6-solid:heading',
  },
  {
    name: 'align',
    label: 'Alinear',
    description: 'Alinea el text (esquerra, centre, dreta, justificat)',
    icon: 'fa6-solid:align-left',
  },
  {
    name: 'fontFamily',
    label: 'Font Family',
    description: 'Selecciona la família de la font',
    icon: 'fa6-solid:font',
  },
  {
    name: 'fontSize',
    label: 'Tamany',
    description: 'Selecciona la mida de la font',
    icon: 'fa6-solid:text-height',
  },
  {
    name: 'textColor',
    label: 'Color del text',
    description: 'Selecciona el color del text',
    icon: 'fa6-solid:palette',
  },
  {
    name: 'bulletList',
    label: 'Llista de vinyetes',
    description: 'Crea una llista no ordenada',
    icon: 'fa6-solid:list-ul',
  },
  {
    name: 'orderedList',
    label: 'Llista numerada',
    description: 'Crea una llista ordenada',
    icon: 'fa6-solid:list-ol',
  },
  {
    name: 'addBlock',
    label: 'Afegeix Bloc',
    description: 'Afegeix un nou bloc d\'editor',
    icon: 'fa6-solid:pen-to-square',
  },
  {
    name: 'table',
    label: 'Taula',
    description: 'Insereix, afegeix o elimina una taula',
    icon: 'fa6-solid:table',
  },
];


export const editorConditions = [
  {
    label: '{% if CONDITION %} TEXT {% endif %}',
    description: "Condició de l'editor. Si la CONDITION es cumpleix, TEXT es mostrarà\nÉs important mantenir els espais entre % i el text",
    icon: 'fa6-solid:rotate-left',
  },
  {
    label: '{% for ITEM in ARRAY %} TEXT {% endfor %}',
    description: "Condició de l'editor. Si ITEM es troba en ARRAY, TEXT es mostrarà per a cada element de l'ARRAY\nÉs important mantenir els espais entre % i el text",
    icon: 'fa6-solid:infinity',
  },
]

export const htmlEditorParts = {
  head: [
    {
      label: 'title',
      description: "Títol de la plantilla",
      icon: 'fa6-solid:heading',
    },
    {
      label: '<style>',
      description: "Estil CSS de la plantilla.", 
      icon: 'fa6-solid:palette',
    },
  ],
  body: [
    {
      label: 'title',
      description: "Títol de la plantilla",
      icon: 'fa6-solid:heading',
    },
  ],
}

export const editorValues = {
  company: [
    {
      label: 'company.name',
      description: "Nom de la empresa",
    },
    {
      label: 'company.address.address_complete',
      description: "Adreça completa de la empresa",
    },
    {
      label: 'company.alias',
      description: "Àlies de la empresa",
    },
  ],
  contract: [
    {
      label: 'contract.token',
      description: "Identificador del contracte",
    },
  ],
  invoice: [
    {
      label: 'invoice.persons_final',
      description: "Persones a l'habitatge",
    },
  ]
}

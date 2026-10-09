export const MessageTypeChoices = {
  'TEXT': 'Text',
  'GRAPHIC': 'Gràfic',
};

export const MessageConditionQuantityDefaultChoices = {
  'contract.contacts': ['pricing_block.adj_contacts', ''],
  'reading.is_estimated': ['billing_block.estimated_reading', ''],
  'date.between': ['pricing_block.adj_date_range', 'date/date-range/'],
};

type TranslateFn = (key: string) => string

export const getMessageVariableGroups = (t: TranslateFn, noContracts = false) => {
  const groups = [
    {
      key: 'recipient',
      title: t('customer_service_block.recipient_variables'),
      notes: [],
      warning: false,
      variables: [
        { token: '%person.token', label: t('common.person_id') },
        { token: '%person.name', label: t('common.name') },
        { token: '%person.address_complete', label: t('address_block.address') },
      ],
    },
    {
      key: 'company',
      title: t('customer_service_block.company_variables'),
      notes: [],
      warning: false,
      variables: [
        { token: '%company.name', label: t('common.name') },
        { token: '%company.phone', label: t('common.tlf') },
        { token: '%company.email', label: t('common.email_long') },
        { token: '%company.address_complete', label: t('address_block.address') },
      ],
    },
    {
      key: 'other',
      title: t('customer_service_block.other_variables'),
      notes: [],
      warning: false,
      variables: [
        { token: '%date.today', label: t('common.today_date') },
        { token: '%communication.due_date', label: t('customer_service_block.send_limit') },
      ],
    },
    {
      key: 'contract',
      title: t('customer_service_block.contract_variables'),
      hidden: noContracts,
      notes: [],
      warning: true,
      variables: [
        { token: '%contract.token', label: t('common.identificator') },
        { token: '%contract.supply_address', label: t('service_block.supply_address') },
        { token: '%contract.previous_daily_consumption', label: t('billing_block.previous_consumption_daily_avg') },
        { token: '%contract.previous_period_consumption', label: t('billing_block.previous_consumption_period_avg') },
      ],
    },
    {
      key: 'invoice',
      title: t('customer_service_block.invoice_variables'),
      notes: [],
      warning: true,
      variables: [
        { token: '%invoice.serie_final', label: t('common.identificator') },
        { token: '%invoice.consumption', label: t('consumption') },
        { token: '%invoice.total', label: t('billing_block.total_amount') },
        { token: '%invoice.due_date', label: t('common.due_date') },
        { token: '%invoice.issue_date', label: t('billing_block.issue_date') },
        /* { token: '%invoice.send_at', label: t('common.send_date') }, */
      ],
    },
    {
      key: 'reading',
      title: t('customer_service_block.reading_variables'),
      notes: [
        {
          text: t('informative_block.info_reading_variables'),
          tone: 'info',
        },
      ],
      warning: true,
      variables: [
        { token: '%reading.data', label: t('billing_block.info_consumption') },
        { token: '%reading.meter_code', label: t('meter') },
        { token: '%reading.reading_value', label: t('reading') },
        { token: '%reading.reading_date', label: t('billing_block.reading_date') },
        { token: '%reading.calculated_value', label: t('consumption') },
        { token: '%reading.leak_value', label: t('billing_block.leak') },
        { token: '%reading.previous_reading_value', label: t('billing_block.previous_reading') },
        { token: '%reading.previous_reading_date', label: t('billing_block.previous_reading_date') },
      ],
    },
  ];

  return groups.filter(group => !group.hidden);
};

export type MessageFormatTag = {
  key: string
  label: string
  token: string
  icon: string
}

export const MESSAGE_FORMAT_TAG_TOKENS = ['BOLD', 'ITALIC', 'UNDERLINE'] as const
export type MessageFormatTagToken = typeof MESSAGE_FORMAT_TAG_TOKENS[number]

const MESSAGE_FORMAT_TAG_PREVIEW_CLASSES: Record<MessageFormatTagToken, string> = {
  BOLD: 'font-bold',
  ITALIC: 'italic',
  UNDERLINE: 'underline',
}

export const getMessageFormatTags = (t: TranslateFn): MessageFormatTag[] => [
  { key: 'bold', label: t('customer_service_block.format_tag_bold'), token: 'BOLD', icon: 'fa6-solid:bold' },
  { key: 'italic', label: t('customer_service_block.format_tag_italic'), token: 'ITALIC', icon: 'fa6-solid:italic' },
  { key: 'underline', label: t('customer_service_block.format_tag_underline'), token: 'UNDERLINE', icon: 'fa6-solid:underline' },
  { key: 'align-right', label: t('customer_service_block.format_tag_align_right'), token: 'ALIGN-RIGHT', icon: 'fa6-solid:align-right' },
  { key: 'align-center', label: t('customer_service_block.format_tag_align_center'), token: 'ALIGN-CENTER', icon: 'fa6-solid:align-center' },
  { key: 'align-left', label: t('customer_service_block.format_tag_align_left'), token: 'ALIGN-LEFT', icon: 'fa6-solid:align-left' },
]

export const escapeHtmlForPreview = (text: string) => text
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Converts known `**TAG**...**TAG**` markers to styled spans. Input must already be HTML-escaped. */
export const applyMessageFormatTagsForPreview = (escapedText: string) => {
  let result = escapedText
  for (const token of MESSAGE_FORMAT_TAG_TOKENS) {
    const marker = escapeRegExp(getMessageFormatTagMarker(token))
    const pattern = new RegExp(`${marker}([\\s\\S]*?)${marker}`, 'g')
    const className = MESSAGE_FORMAT_TAG_PREVIEW_CLASSES[token]
    result = result.replace(pattern, `<span class="${className}">$1</span>`)
  }
  return result
}

/** Safe HTML for message preview: escape user content, then apply known format tags and variable highlights. */
export const formatMessageTextForPreview = (text: string) => {
  if (!text) return ''

  let result = escapeHtmlForPreview(text)
  result = result.replace(/\n/g, '<br>')
  result = applyMessageFormatTagsForPreview(result)
  result = result.replace(/(%[a-zA-Z]+\.[a-zA-Z_]+)/g, '<span class="font-bold italic text-sky-600">$1</span>')
  return result
}

export const getMessageFormatTagMarker = (token: string) => `**${token}**`

export const wrapTextWithMessageFormatTag = (
  text: string,
  selectionStart: number,
  selectionEnd: number,
  token: string,
) => {
  const marker = getMessageFormatTagMarker(token)
  const selected = text.substring(selectionStart, selectionEnd)
  const wrapped = marker + selected + marker
  const newText = text.substring(0, selectionStart) + wrapped + text.substring(selectionEnd)
  const cursorStart = selectionStart + marker.length
  const cursorEnd = cursorStart + selected.length

  return { text: newText, selectionStart: cursorStart, selectionEnd: cursorEnd }
}

export const applyMessageFormatTagToTextarea = (
  body: { value: string },
  token: string,
  textareaId = 'messageTextarea',
) => {
  const textarea = document.getElementById(textareaId) as HTMLTextAreaElement | null
  if (!textarea) return

  const { text, selectionStart, selectionEnd } = wrapTextWithMessageFormatTag(
    body.value,
    textarea.selectionStart,
    textarea.selectionEnd,
    token,
  )

  body.value = text
  textarea.value = text
  textarea.selectionStart = selectionStart
  textarea.selectionEnd = selectionEnd
  textarea.focus()
}

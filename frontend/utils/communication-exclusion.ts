type TranslateFn = (key: string) => string

// Pla de numeració espanyol: mòbils 6xx xxx xxx i 71x-74x xxx xxx. Mateix
// criteri que backend/coredata/utils/phone_utils.py (is_mobile_phone).
const SPANISH_MOBILE_RE = /^(6\d{8}|7[1-4]\d{7})$/

export const isMobilePhone = (phone?: string | null): boolean => {
  if (!phone) return false
  // Sense separadors ni parèntesis, perquè '(+34) 612...' també porti prefix.
  const value = String(phone).replace(/[^\d+]/g, '')
  const international = value.startsWith('+') || value.startsWith('00')
  let digits = value.replace(/\D/g, '')
  if (value.startsWith('00')) digits = digits.slice(2)
  if (!digits) return false
  if (international) {
    // Dels números estrangers no es pot saber si són fixos.
    if (!digits.startsWith('34')) return digits.length >= 8 && digits.length <= 15
    digits = digits.slice(2)
  }
  return SPANISH_MOBILE_RE.test(digits)
}

// Motius pels quals un destinatari no rep un canal (codis del backend).
export const exclusionReasonLabel = (t: TranslateFn, reason: string): string =>
  t(`customer_service_block.exclusion_reasons.${reason}`)

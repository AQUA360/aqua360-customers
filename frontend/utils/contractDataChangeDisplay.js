/** Resuelve el id de un valor que puede ser un id numérico o un objeto con `id`. */
export function resolveId(value) {
  if (value == null) return null;
  if (typeof value === 'object') return value.id ?? null;
  return value;
}

function extractEmail(value) {
  if (value == null) return null;
  if (typeof value === 'object') return value.email ?? null;
  return null;
}

function extractPhone(value) {
  if (value == null) return null;
  if (typeof value === 'object') return value.phone ?? null;
  return null;
}

function extractAddressComplete(value) {
  if (value == null) return null;
  if (typeof value === 'object') return value.address_complete ?? null;
  return null;
}

/** Normalitza una llista de contactes/telèfons a ids ordenats. */
export function toSortedPhoneIds(phones) {
  if (!Array.isArray(phones)) return [];
  return phones.map((p) => resolveId(p)).filter((id) => id != null).sort((a, b) => a - b);
}

function contractDataPhoneIdsChanged(newPhones, previousPhones) {
  const newIds = toSortedPhoneIds(newPhones);
  const prevIds = toSortedPhoneIds(previousPhones);
  if (newIds.length === 0 && prevIds.length === 0) return false;
  return JSON.stringify(newIds) !== JSON.stringify(prevIds);
}

/** Normalitza text de telèfons per comparar (tracta '-' com a buit). */
export function normalizePhoneDisplayText(value) {
  if (value == null || value === '' || value === '-') return '';
  return String(value).trim();
}

/** Camps de telèfon en logs contract-data (el serializer pot variar). */
export function extractContractDataLogPhones(log) {
  if (!log) return { previous: null, current: null };
  return {
    previous: log.previous_phone ?? log.previous_phones ?? log.phone_previous ?? null,
    current: log.current_phone ?? log.current_phones ?? log.phone_current ?? null,
  };
}

export function isContractDataPhoneLog(log) {
  const { previous, current } = extractContractDataLogPhones(log);
  return normalizePhoneDisplayText(previous) !== normalizePhoneDisplayText(current);
}

/** Text per mostrar una llista de telèfons (ex. "666111222, 666333444"). */
export function formatPhonesDisplay(phones) {
  if (!Array.isArray(phones) || phones.length === 0) return null;
  const numbers = phones
    .map((p) => (typeof p === 'object' ? p.phone : null))
    .filter((n) => n);
  return numbers.length > 0 ? numbers.join(', ') : null;
}

/** Detecta canvi de telèfon(s) en un registre de data_change. */
export function contractDataPhonesChangedForRecord(record) {
  if (!record) return false;

  if (record.phones_display_previous != null || record.phones_display_new != null) {
    return normalizePhoneDisplayText(record.phones_display_previous)
      !== normalizePhoneDisplayText(record.phones_display_new);
  }

  if (record.new_phone_ids != null || record.previous_phone_ids != null) {
    return contractDataPhoneIdsChanged(record.new_phone_ids, record.previous_phone_ids);
  }

  if (record.new_contact_phones != null || record.previous_contact_phones != null) {
    return contractDataPhoneIdsChanged(record.new_contact_phones, record.previous_contact_phones);
  }

  return contractDataPersonContactPhoneChanged(
    record.new_person_contact_phone,
    record.previous_person_contact_phone
  );
}

/** Valors previous/new per mostrar al detall del canvi de telèfons. */
export function getPhonesChangeDisplay(record) {
  if (record?.phones_display_previous != null || record?.phones_display_new != null) {
    return {
      previous: record.phones_display_previous || null,
      new: record.phones_display_new || null,
    };
  }

  if (record?.new_phone_ids != null || record?.previous_phone_ids != null) {
    const fromContacts = {
      previous: formatPhonesDisplay(record.previous_contact_phones),
      new: formatPhonesDisplay(record.new_contact_phones),
    };
    if (fromContacts.previous || fromContacts.new) return fromContacts;
  }

  if (record?.new_contact_phones != null || record?.previous_contact_phones != null) {
    return {
      previous: formatPhonesDisplay(record.previous_contact_phones),
      new: formatPhonesDisplay(record.new_contact_phones),
    };
  }

  return {
    previous: extractPhone(record?.previous_person_contact_phone),
    new: extractPhone(record?.new_person_contact_phone),
  };
}

export function contractDataPaymentChanged(newPayment, previousPayment) {
  if (newPayment == null && previousPayment == null) return false;

  const newId = resolveId(newPayment);
  const prevId = resolveId(previousPayment);
  if (newId != null && prevId != null && newId === prevId) return false;

  const newIban = newPayment && typeof newPayment === 'object' ? newPayment.iban : null;
  const prevIban = previousPayment && typeof previousPayment === 'object' ? previousPayment.iban : null;
  if (newIban != null && prevIban != null) return newIban !== prevIban;
  if (newIban && !prevIban) return true;
  if (!newIban && prevIban) return true;

  return newId !== prevId;
}

export function contractDataAddressChanged(newAddress, previousAddress) {
  if (newAddress == null && previousAddress == null) return false;

  const newComplete = extractAddressComplete(newAddress);
  const prevComplete = extractAddressComplete(previousAddress);
  if (newComplete && !prevComplete) return true;
  if (!newComplete && prevComplete) return true;
  if (newComplete != null && prevComplete != null) return newComplete !== prevComplete;

  const newId = resolveId(newAddress);
  const prevId = resolveId(previousAddress);
  if (newId != null && prevId != null && newId === prevId) return false;

  return newId !== prevId;
}

export function contractDataPaymentTypeChanged(newType, previousType) {
  if (!newType) return false;

  const newId = resolveId(newType);
  const prevId = resolveId(previousType);
  if (newId != null && prevId != null && newId === prevId) return false;

  const newName = newType && typeof newType === 'object' ? newType.name : null;
  const prevName = previousType && typeof previousType === 'object' ? previousType.name : null;
  if (newName != null && prevName != null) return newName !== prevName;
  if (newName && !prevName) return true;

  return newId !== prevId;
}

export function contractDataPersonContactEmailChanged(newEmail, previousEmail) {
  if (!newEmail) return false;

  const newEmailStr = extractEmail(newEmail);
  const prevEmailStr = extractEmail(previousEmail);
  if (newEmailStr && !prevEmailStr) return true;
  if (!newEmailStr && prevEmailStr) return true;
  if (newEmailStr != null && prevEmailStr != null) return newEmailStr !== prevEmailStr;

  const newId = resolveId(newEmail);
  const prevId = resolveId(previousEmail);
  if (newId != null && prevId != null && newId === prevId) return false;
  if (newId != null && prevId == null) return true;

  return newId !== prevId;
}

export function contractDataTotalPersonsChanged(newTotal, previousTotal) {
  if (newTotal == null && previousTotal == null) return false;
  if (newTotal != null && previousTotal != null) return Number(newTotal) !== Number(previousTotal);
  return newTotal != null || previousTotal != null;
}

/** Converteix un registre del logger contract-data (telèfons) al format de DataChange. */
export function mapContractDataLogPhonesToDataChange(log) {
  if (!isContractDataPhoneLog(log)) return null;

  const { previous, current } = extractContractDataLogPhones(log);

  return {
    id: `contract-phones-${log.id}`,
    created_at: log.timestamp,
    approved_at: log.timestamp,
    user: log.user,
    phones_display_previous: previous ?? '',
    phones_display_new: current ?? '',
  };
}

/** Converteix un registre del logger contract-total-members al format de DataChange. */
export function mapMembersLogToDataChange(memberLog) {
  return {
    id: `members-${memberLog.id}`,
    created_at: memberLog.timestamp,
    approved_at: memberLog.timestamp,
    user: memberLog.user,
    new_total_persons: memberLog.current_total_persons,
    previous_total_persons: memberLog.previous_total_persons,
  };
}

const MERGE_WINDOW_MS = 2 * 60 * 1000;

function entryTimestamp(entry) {
  return new Date(entry?.created_at || entry?.approved_at || entry?.timestamp || 0).getTime();
}

function findClosestModificationEntry(entries, logTime) {
  let best = null;
  let bestDiff = MERGE_WINDOW_MS + 1;

  for (const entry of entries) {
    const diff = Math.abs(entryTimestamp(entry) - logTime);
    if (diff <= MERGE_WINDOW_MS && diff < bestDiff) {
      bestDiff = diff;
      best = entry;
    }
  }

  return best;
}

function phoneDisplayAlreadyVisible(entries, mapped) {
  const prev = normalizePhoneDisplayText(mapped.phones_display_previous);
  const next = normalizePhoneDisplayText(mapped.phones_display_new);

  return entries.some((dc) => {
    if (!contractDataPhonesChangedForRecord(dc)) return false;
    const display = getPhonesChangeDisplay(dc);
    return normalizePhoneDisplayText(display.previous) === prev
      && normalizePhoneDisplayText(display.new) === next;
  });
}

function hasSameTotalPersonsChange(a, b) {
  return contractDataTotalPersonsChanged(a?.new_total_persons, a?.previous_total_persons)
    && contractDataTotalPersonsChanged(b?.new_total_persons, b?.previous_total_persons)
    && Number(a.new_total_persons) === Number(b.new_total_persons)
    && Number(a.previous_total_persons) === Number(b.previous_total_persons);
}

/** Incorpora camps de persones d'un altre registre al mateix canvi. */
function absorbMembersFields(target, source) {
  if (source.new_total_persons != null) target.new_total_persons = source.new_total_persons;
  if (source.previous_total_persons != null) target.previous_total_persons = source.previous_total_persons;
  if (!target.user && source.user) target.user = source.user;
}

/**
 * Fusiona data_changes amb logs de persones al mateix registre quan són del mateix guardat.
 * Només mostra una entrada separada si és un log històric sense canvi associat.
 */
export function mergeContractModifications(dataChanges, membersLogs, contractDataLogs = []) {
  const merged = (dataChanges || []).map((dc) => ({ ...dc }));

  for (const log of contractDataLogs || []) {
    const mapped = mapContractDataLogPhonesToDataChange(log);
    if (!mapped) continue;

    const logTime = entryTimestamp(mapped);
    const target = findClosestModificationEntry(merged, logTime);

    if (target && !contractDataPhonesChangedForRecord(target)) {
      target.phones_display_previous = mapped.phones_display_previous;
      target.phones_display_new = mapped.phones_display_new;
    }

    if (!phoneDisplayAlreadyVisible(merged, mapped)) {
      merged.push(mapped);
    }
  }

  for (const log of membersLogs || []) {
    const mapped = mapMembersLogToDataChange(log);

    if (merged.some((dc) => hasSameTotalPersonsChange(dc, mapped))) {
      continue;
    }

    const logTime = entryTimestamp(mapped);
    const target = findClosestModificationEntry(merged, logTime);

    if (target) {
      absorbMembersFields(target, mapped);
      continue;
    }

    merged.push(mapped);
  }

  return merged
    .sort((a, b) => entryTimestamp(b) - entryTimestamp(a))
    .filter((entry) => contractDataModificationHasVisibleContent(entry));
}

/** Indica si el registre té algun camp que es pugui mostrar a DataChange. */
export function contractDataModificationHasVisibleContent(record) {
  if (!record) return false;

  return contractDataPaymentTypeChanged(record.new_payment_type, record.previous_payment_type)
    || contractDataPaymentChanged(record.new_payment, record.previous_payment)
    || contractDataAddressChanged(record.new_address_billing, record.previous_address_billing)
    || contractDataAddressChanged(record.new_address_contact, record.previous_address_contact)
    || contractDataPersonContactEmailChanged(record.new_person_contact_email, record.previous_person_contact_email)
    || contractDataTotalPersonsChanged(record.new_total_persons, record.previous_total_persons)
    || contractDataPhonesChangedForRecord(record);
}

export function contractDataPersonContactPhoneChanged(newPhone, previousPhone) {
  if (!newPhone && !previousPhone) return false;
  if (!newPhone && previousPhone) return true;

  const newNumber = extractPhone(newPhone);
  const prevNumber = extractPhone(previousPhone);
  if (newNumber && !prevNumber) return true;
  if (!newNumber && prevNumber) return true;
  if (newNumber != null && prevNumber != null) return newNumber !== prevNumber;

  const newId = resolveId(newPhone);
  const prevId = resolveId(previousPhone);
  if (newId != null && prevId != null && newId === prevId) return false;
  if (newId != null && prevId == null) return true;

  return newId !== prevId;
}

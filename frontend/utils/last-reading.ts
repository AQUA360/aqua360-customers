// ~/utils/last-reading.ts

type ReadingLike = { is_control?: boolean; reading_value?: string | number | null };

type ReadingPage<T> = { results?: T[]; next?: string | null } | null | undefined;

type ReadingApi<T> = {
  getAll: (...args: any[]) => Promise<ReadingPage<T>>;
};

const isBillable = (reading: ReadingLike) => !reading.is_control && reading.reading_value != null;

/**
 * Separa l'última lectura facturable de les lectures de control més recents.
 *
 * Les lectures han d'arribar ordenades de la més recent a la més antiga (ordre per
 * defecte de l'API de lectures). Les de control no es facturen, però poden ser el
 * valor més recent del comptador: es retornen a part perquè l'usuari les tingui en compte.
 * Les lectures sense valor no compten com a última lectura.
 */
export const splitLastReading = <T extends ReadingLike>(readings: T[] | null | undefined) => {
  const list = readings ?? [];
  const index = list.findIndex(isBillable);
  return {
    reading: index >= 0 ? list[index] : null,
    newerControlReadings: (index >= 0 ? list.slice(0, index) : list).filter((reading) => reading.is_control),
  };
};

/**
 * Obté l'última lectura facturable d'un punt de subministrament (i contractes) i les
 * lectures de control més recents. Si la primera pàgina no en té cap de facturable,
 * la busca directament entre les que no són de control.
 */
export const fetchLastReading = async <T extends ReadingLike>(
  readingApi: ReadingApi<T>,
  { contractIds = [], supplyPointId }: { contractIds?: (number | string)[]; supplyPointId: number | string },
) => {
  const response = await readingApi.getAll('', [], 1, null, false, contractIds, supplyPointId);
  const split = splitLastReading(response?.results);
  if (split.reading || !response?.next) return split;

  const billable = await readingApi.getAll('', [], 1, null, false, contractIds, supplyPointId, null, false);
  return { ...split, reading: splitLastReading(billable?.results).reading };
};

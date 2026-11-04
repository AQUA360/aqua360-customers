// ~/utils/last-reading.ts

type ReadingLike = { is_control?: boolean };

/**
 * Separa l'última lectura facturable de les lectures de control més recents.
 *
 * Les lectures han d'arribar ordenades de la més recent a la més antiga (ordre per
 * defecte de l'API de lectures). Les de control no es facturen, però poden ser el
 * valor més recent del comptador: es retornen a part perquè l'usuari les tingui en compte.
 */
export const splitLastReading = <T extends ReadingLike>(readings: T[] | null | undefined) => {
  const list = readings ?? [];
  const index = list.findIndex((reading) => !reading.is_control);
  return {
    reading: index >= 0 ? list[index] : null,
    newerControlReadings: (index >= 0 ? list.slice(0, index) : list).filter((reading) => reading.is_control),
  };
};

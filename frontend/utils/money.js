

/* *
 * Formats an import string into a float with two decimals format.
 */
export const formatMoney = (input) => {
    return parseFloat(input).toFixed(2);
}

export const formatMoneyWithCurrency = (input) => {
    return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
        input,
      )
}
/* *
 * Normalitza un import escrit a mà per enviar-lo com a paràmetre numèric a
 * l'API. Accepta les formes amb què s'escriu un total ("1.234,56", "1234,56",
 * "1234.56", "1234") i retorna null si no en surt un número, de manera que el
 * filtre simplement no s'apliqui: els filtres numèrics del backend
 * (`NumberFilter`) responen 400 si reben text que no és un número.
 */
export const parseAmountInput = (input) => {
    if (input === null || input === undefined) return null;

    const raw = String(input).trim();
    if (raw === '') return null;

    const lastComma = raw.lastIndexOf(',');
    const lastDot = raw.lastIndexOf('.');

    let normalised;
    if (lastComma > -1 && lastDot > -1) {
        // Amb els dos separadors, el darrer és el decimal i l'altre és de milers.
        const decimalSeparator = lastComma > lastDot ? ',' : '.';
        const thousandSeparator = decimalSeparator === ',' ? '.' : ',';
        normalised = raw.split(thousandSeparator).join('').replace(decimalSeparator, '.');
    } else if (lastComma > -1 || lastDot > -1) {
        // Amb un sol separador és ambigu: en un import, tres decimals no
        // existeixen, així que "1.234" i "1,234" són milers i "12,3"/"12.34"
        // són decimals.
        const separator = lastComma > -1 ? ',' : '.';
        const decimals = raw.length - raw.lastIndexOf(separator) - 1;
        normalised = decimals === 3
            ? raw.split(separator).join('')
            : raw.replace(separator, '.');
    } else {
        normalised = raw;
    }

    normalised = normalised.replace(/[^0-9.-]/g, '');
    if (normalised === '' || normalised === '.' || normalised === '-') return null;

    const value = Number(normalised);

    return Number.isFinite(value) ? String(value) : null;
}

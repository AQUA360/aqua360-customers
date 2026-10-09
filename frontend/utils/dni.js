const DNI_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE';

/**
 * Valida un DNI espanyol (8 dígits + lletra de control).
 * Retorna true/false. No llença excepcions, no bloqueja res.
 */
export function isValidDNI(value) {
  if (!value) return false;
  const clean = String(value).trim().toUpperCase().replace(/[\s-]/g, '');

  const match = clean.match(/^(\d{8})([A-Z])$/);
  if (!match) return false;

  const [, digits, letter] = match;
  const expectedLetter = DNI_LETTERS[parseInt(digits, 10) % 23];

  return letter === expectedLetter;
}
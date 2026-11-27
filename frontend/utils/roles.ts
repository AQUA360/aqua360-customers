/** Compte tècnic: sempre superusuari i l'únic que dona o treu el rol de superusuari. */
export const CANONICAL_SUPERUSER_USERNAME = 'customers';

export type UserRole = 'superuser' | 'admin' | 'none';

type RoleUser = {
  role?: string | null;
  username?: string | null;
  is_superuser?: boolean;
  is_staff?: boolean;
} | null | undefined;

export function getUserRole(user: RoleUser): UserRole {
  if (!user) return 'none';
  if (user.role === 'superuser' || user.role === 'admin' || user.role === 'none') {
    return user.role;
  }
  if (user.is_superuser && user.username === CANONICAL_SUPERUSER_USERNAME) {
    return 'superuser';
  }
  if (user.is_staff || user.is_superuser) {
    return 'admin';
  }
  return 'none';
}

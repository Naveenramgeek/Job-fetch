import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Allows access only when authenticated AND in temp password mode (requires password change). */
export const changePasswordGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated) {
    router.navigate(['/auth/login']);
    return false;
  }
  if (!auth.requiresPasswordChange) {
    router.navigate(['/dashboard']);
    return false;
  }
  return true;
};

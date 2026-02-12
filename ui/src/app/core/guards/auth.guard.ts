import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated) {
    router.navigate(['/auth/login']);
    return false;
  }
  if (auth.requiresPasswordChange) {
    router.navigate(['/auth/change-password']);
    return false;
  }
  return true;
};

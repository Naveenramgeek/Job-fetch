import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { adminGuard } from './core/guards/admin.guard';
import { authGuard } from './core/guards/auth.guard';
import { guestGuard } from './core/guards/guest.guard';
import { ShellComponent } from './shared/layout/shell/shell.component';

const routes: Routes = [
  { path: 'login', redirectTo: 'auth/login', pathMatch: 'full' },
  { path: 'signup', redirectTo: 'auth/signup', pathMatch: 'full' },
  {
    path: '',
    loadChildren: () => import('./features/landing/landing.module').then((m) => m.LandingModule),
    canActivate: [guestGuard],
  },
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.module').then((m) => m.AuthModule),
  },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      { path: 'dashboard', loadChildren: () => import('./features/dashboard/dashboard.module').then((m) => m.DashboardModule) },
      { path: 'resume', loadChildren: () => import('./features/resume/resume.module').then((m) => m.ResumeModule) },
      { path: 'tailor-resume', loadChildren: () => import('./features/tailor-resume/tailor-resume.module').then((m) => m.TailorResumeModule) },
      { path: 'account', loadChildren: () => import('./features/account/account.module').then((m) => m.AccountModule) },
      { path: 'admin', loadChildren: () => import('./features/admin/admin.module').then((m) => m.AdminModule), canActivate: [adminGuard] },
    ],
  },
  { path: '**', redirectTo: '' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { useHash: false })],
  exports: [RouterModule],
})
export class AppRoutingModule {}

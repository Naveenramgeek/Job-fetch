import { NgModule } from '@angular/core';
import { CanDeactivateFn, RouterModule, Routes } from '@angular/router';
import { ResumePageComponent } from './resume-page/resume-page.component';

const resumeUnsavedChangesGuard: CanDeactivateFn<ResumePageComponent> = (component) => component.canDeactivate();

const routes: Routes = [
  { path: '', component: ResumePageComponent, canDeactivate: [resumeUnsavedChangesGuard] },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ResumeRoutingModule {}

import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ResumePageComponent } from './resume-page/resume-page.component';

const routes: Routes = [
  { path: '', component: ResumePageComponent },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ResumeRoutingModule {}

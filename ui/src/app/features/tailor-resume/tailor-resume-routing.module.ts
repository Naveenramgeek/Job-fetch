import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { TailorResumePageComponent } from './tailor-resume-page/tailor-resume-page.component';

const routes: Routes = [
  { path: '', component: TailorResumePageComponent },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class TailorResumeRoutingModule {}

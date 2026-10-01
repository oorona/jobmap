import type {Job} from './types';
export type Filters={location:string;workMode:string;salaryOnly:boolean;minimum:string;currency:string;period:string};
export const defaultFilters:Filters={location:'',workMode:'',salaryOnly:false,minimum:'',currency:'USD',period:'year'};
const countryNames:Record<string,string>={MX:'Mexico',US:'United States USA',CA:'Canada',GB:'United Kingdom UK',DE:'Germany',worldwide:'Worldwide'};
export function filterJobs(jobs:Job[],filters:Filters){
 const location=filters.location.trim().toLowerCase();const minimum=Number(filters.minimum);
 return jobs.filter(job=>{
  if(location){const countries=job.eligible_countries.status==='unknown'?[]:Array.isArray(job.eligible_countries.value)?job.eligible_countries.value:[];const text=[job.location?.status!=='unknown'?JSON.stringify(job.location?.value??''):'',...countries.map(c=>`${c} ${countryNames[String(c)]??''}`)].join(' ').toLowerCase();if(!text.includes(location))return false;}
  if(filters.workMode){const values=Array.isArray(job.work_mode.value)?job.work_mode.value:[job.work_mode.value];if(job.work_mode.status==='unknown'||!values.includes(filters.workMode))return false;}
  const salary=job.compensation.value as {min?:number;max?:number;currency?:string;period?:string|null;original?:string}|null;
  if(filters.salaryOnly&&(job.compensation.status==='unknown'||!salary))return false;
  if(filters.minimum.trim()){
   if(!Number.isFinite(minimum)||minimum<0||job.compensation.status==='unknown'||!salary||typeof salary.min!=='number'||salary.min<minimum||salary.currency!==filters.currency||(salary.period??'unknown')!==filters.period)return false;
  }
  return true;
 });
}

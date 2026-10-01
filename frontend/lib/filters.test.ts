import {it,expect} from 'vitest';
import {filterJobs,defaultFilters} from './filters';
import fixtures from '../fixtures/jobs.json';
import type {Job} from './types';
const base=fixtures[0] as unknown as Job;
const paid={...base,location:{status:'stated' as const,value:'Mexico City',evidence_ids:[]},work_mode:{status:'stated' as const,value:['remote','hybrid'],evidence_ids:[]},compensation:{status:'stated' as const,value:{min:100000,max:180000,currency:'USD',period:'year'},evidence_ids:[]}};
it('combines location, multi-mode arrangements and minimum stated pay',()=>{expect(filterJobs([paid],{...defaultFilters,location:'Mexico',workMode:'remote',minimum:'90000'})).toEqual([paid]);expect(filterJobs([paid],{...defaultFilters,minimum:'150000'})).toEqual([]);});
it('does not compare different currencies, periods, or unknown salary evidence',()=>{expect(filterJobs([paid],{...defaultFilters,currency:'MXN',minimum:'1'})).toEqual([]);expect(filterJobs([paid],{...defaultFilters,period:'hour',minimum:'1'})).toEqual([]);expect(filterJobs([{...paid,compensation:{status:'unknown',value:null,evidence_ids:[]}}],{...defaultFilters,salaryOnly:true})).toEqual([]);expect(filterJobs([{...paid,compensation:{...paid.compensation,value:{min:100000,currency:'USD',period:null}}}],{...defaultFilters,minimum:'1'})).toEqual([]);});

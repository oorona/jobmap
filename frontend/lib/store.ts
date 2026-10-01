'use client';
import {create} from 'zustand';
import {persist} from 'zustand/middleware';
import type {Preferences} from './types';
type Store={bookmarks:string[];saved:string[];preferences:Preferences;bookmark:(id:string)=>void;save:(q:string)=>void;setPreferences:(p:Preferences)=>void};
export const useLocal=create<Store>()(persist(set=>({bookmarks:[],saved:[],preferences:{remote:false,country:'',weights:{}},bookmark:id=>set(s=>({bookmarks:s.bookmarks.includes(id)?s.bookmarks.filter(x=>x!==id):[...s.bookmarks,id]})),save:q=>set(s=>({saved:s.saved.includes(q)?s.saved.filter(x=>x!==q):[...s.saved,q].slice(-20)})),setPreferences:preferences=>set({preferences})}),{name:'jev-device-v2',skipHydration:true}));

import { auth, profile, pathways, eligibility, qa, plans, schools } from '../mocks'
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const useMock = import.meta.env.VITE_USE_MOCK !== 'false'
const TOKEN_KEY='access_token'
export const getToken=()=>localStorage.getItem(TOKEN_KEY)
export const setToken=(t:string)=>localStorage.setItem(TOKEN_KEY,t)
export const clearToken=()=>localStorage.removeItem(TOKEN_KEY)
const qs=(q?:Record<string,string|undefined>)=>{const p=Object.entries(q||{}).filter(([,v])=>v!==undefined&&v!=='')as[string,string][];return p.length?'?'+p.map(([k,v])=>`${k}=${encodeURIComponent(v)}`).join('&'):''}
async function request<T>(path:string,init?:RequestInit):Promise<Zhixuan.ApiResponse<T>> { const token=getToken(); const r=await fetch(`${API_BASE}${path}`,{...init,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{}) ,...(init?.headers||{})}}); if(!r.ok) throw new Error(`API ${r.status}`); return r.json() }
const pick=<T>(value:Zhixuan.ApiResponse<T>)=>Promise.resolve(value)
export const api={
 health:()=>request<{status:string}>('/api/health'),
 register:(p:{username:string;password:string})=>useMock?pick(auth.success):request('/api/auth/register',{method:'POST',body:JSON.stringify(p)}),
 login:(p:{username:string;password:string})=>useMock?pick(auth.success):request('/api/auth/login',{method:'POST',body:JSON.stringify(p)}),
 logout:()=>useMock?pick(auth.logout):request('/api/auth/logout',{method:'POST'}),
 me:()=>useMock?pick(auth.me):request<Zhixuan.User>('/api/auth/me'),
 getProfile:()=>useMock?pick(profile.success):request<Zhixuan.Profile>('/api/user/profile'),
 updateProfile:(p:Zhixuan.Profile)=>useMock?pick(profile.success):request('/api/user/profile',{method:'PUT',body:JSON.stringify(p)}),
 deleteAccount:(p:{password:string})=>useMock?pick(profile.deleted):request('/api/user',{method:'DELETE',body:JSON.stringify(p)}),
 pathways:(q?:{category?:string;priority?:'P0'|'P1'|'P2';status?:string})=>useMock?pick(pathways.success):request<Zhixuan.Pathway[]>(`/api/pathways${qs(q)}`),
 pathwayDetail:(id:string)=>useMock?pick(pathways.detail):request<Zhixuan.Pathway>(`/api/pathways/${encodeURIComponent(id)}`),
 regionCheck:(p:{province:string;county:string})=>useMock?pick(pathways.regionCheck):request<Zhixuan.RegionCheck>(`/api/pathways/region-check${qs({province:p.province,county:p.county})}`),
 eligibility:(p:Zhixuan.Profile)=>useMock?pick(eligibility.pending):request<Zhixuan.Eligibility>('/api/pathways/eligibility-check',{method:'POST',body:JSON.stringify(p)}),
 qa:(q:string)=>useMock?pick(qa.success):request<Zhixuan.QaResult>(`/api/qa${qs({q})}`),
 plans:(p:Zhixuan.PlanRequest)=>useMock?pick(plans.success):request<Zhixuan.PlanResult>('/api/plans',{method:'POST',body:JSON.stringify(p)}),
 schools:(keyword='',province='河南')=>useMock?pick(schools.success):request<Zhixuan.School[]>(`/api/schools${qs({keyword,province})}`)
}

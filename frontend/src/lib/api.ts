export const API=import.meta.env.VITE_API_URL||'';
export async function api<T>(path:string, init?:RequestInit):Promise<T>{const r=await fetch(API+path,{headers:{'Content-Type':'application/json',...(init?.headers||{})},...init});if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail)||'Request failed')}return r.json()}
export const post=<T>(path:string,body?:unknown)=>api<T>(path,{method:'POST',body:body?JSON.stringify(body):undefined});

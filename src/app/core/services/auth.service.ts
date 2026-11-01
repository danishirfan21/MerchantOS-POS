import { inject, Injectable, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, switchMap, tap, throwError } from 'rxjs';
export interface AuthUser { id: string; username: string; role: string; }
@Injectable({providedIn:'root'})
export class AuthService {
 readonly replacementRequired=signal(false); readonly http=inject(HttpClient); readonly user=signal<AuthUser|null>(null); readonly ready=signal(false); token='';
 csrf(){return this.http.get<{token:string}>('/api/auth/csrf').pipe(tap(r=>this.token=r.token));}
 load(){this.http.get<AuthUser>('/api/auth/me').subscribe({next:u=>{this.user.set(u.role==='Cashier'?u:null);this.csrf().subscribe({next:()=>this.ready.set(true),error:()=>{this.user.set(null);this.ready.set(true);}});},error:()=>{this.user.set(null);this.ready.set(true);}});}
 login(username:string,password:string){return this.csrf().pipe(switchMap(()=>this.http.post<AuthUser & {step?:string;mustChangePassword?:boolean}>('/api/auth/login',{username,password})),switchMap(u=>{
  if(u.step==='password'&&u.mustChangePassword){this.replacementRequired.set(true);return this.csrf();}
  if(u.step){return this.http.post('/api/auth/mfa/cancel',{}).pipe(switchMap(()=>throwError(()=>new Error('Use the Administrator interface.'))));}
  if(u.role!=='Cashier')return this.csrf().pipe(switchMap(()=>this.http.post('/api/auth/logout',{})),switchMap(()=>throwError(()=>new Error('Cashier access is required.'))));
  return this.csrf().pipe(tap(()=>this.user.set(u)));
 }));}
 replacePassword(newPassword:string){return this.csrf().pipe(switchMap(()=>this.http.post<{user:AuthUser}>('/api/auth/mfa/complete',{newPassword})),switchMap(result=>this.csrf().pipe(tap(()=>{this.user.set(result.user);this.replacementRequired.set(false);})))) ;}
 cancelReplacement(){return this.csrf().pipe(switchMap(()=>this.http.post('/api/auth/mfa/cancel',{})),tap(()=>this.replacementRequired.set(false)));}
 logout(){return this.csrf().pipe(switchMap(()=>this.http.post('/api/auth/logout',{})),tap(()=>this.user.set(null)));}
}
export const sessionInterceptor:HttpInterceptorFn=(request,next)=>{
 const auth=inject(AuthService);
 if(request.url.startsWith('/api/')&&request.method!=='GET'&&auth.token) request=request.clone({setHeaders:{'X-CSRF-TOKEN':auth.token}});
 return next(request).pipe(catchError((error:HttpErrorResponse)=>{if(error.status===401&&!request.url.includes('/auth/login')){auth.user.set(null);auth.ready.set(true);}return throwError(()=>error);}));
};

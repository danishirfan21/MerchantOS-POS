import { inject, Injectable, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, switchMap, tap, throwError } from 'rxjs';
export interface AuthUser { id: string; username: string; role: string; }
@Injectable({providedIn:'root'})
export class AuthService {
 readonly http=inject(HttpClient); readonly user=signal<AuthUser|null>(null); readonly ready=signal(false); token='';
 csrf(){return this.http.get<{token:string}>('/api/auth/csrf').pipe(tap(r=>this.token=r.token));}
 load(){this.http.get<AuthUser>('/api/auth/me').subscribe({next:u=>{this.user.set(u.role==='Cashier'?u:null);this.csrf().subscribe({next:()=>this.ready.set(true),error:()=>{this.user.set(null);this.ready.set(true);}});},error:()=>{this.user.set(null);this.ready.set(true);}});}
 login(username:string,password:string){return this.csrf().pipe(switchMap(()=>this.http.post<AuthUser>('/api/auth/login',{username,password})),switchMap(u=>{
  if(u.role!=='Cashier')return this.csrf().pipe(switchMap(()=>this.http.post('/api/auth/logout',{})),switchMap(()=>throwError(()=>new Error('Cashier access is required.'))));
  return this.csrf().pipe(tap(()=>this.user.set(u)));
 }));}
 logout(){return this.csrf().pipe(switchMap(()=>this.http.post('/api/auth/logout',{})),tap(()=>this.user.set(null)));}
}
export const sessionInterceptor:HttpInterceptorFn=(request,next)=>{
 const auth=inject(AuthService);
 if(request.url.startsWith('/api/')&&request.method!=='GET'&&auth.token) request=request.clone({setHeaders:{'X-CSRF-TOKEN':auth.token}});
 return next(request).pipe(catchError((error:HttpErrorResponse)=>{if(error.status===401&&!request.url.includes('/auth/login')){auth.user.set(null);auth.ready.set(true);}return throwError(()=>error);}));
};

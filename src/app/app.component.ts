import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from './core/services/auth.service';
import { CheckoutComponent } from './features/checkout/components/checkout.component';
@Component({selector:'mos-root',standalone:true,imports:[CheckoutComponent,FormsModule],template:`
@if(!auth.ready()){<main class="auth-screen"><p>Checking session…</p></main>}
@else if(auth.user()){
 @if(error()){<p role="alert">{{error()}}</p>}<mos-checkout [username]="auth.user()?.username ?? ''" (signOut)="logout()" />
}@else if(auth.replacementRequired()){
 <main class="auth-screen"><form class="auth-card" (ngSubmit)="replacePassword()"><h1>Replace temporary password</h1><p>Choose a different password of 14–128 characters before using POS.</p>
 <label for="replacement">New password</label><input id="replacement" name="replacement" type="password" autocomplete="new-password" minlength="14" maxlength="128" [(ngModel)]="replacement" required>
 <label for="confirmation">Confirm password</label><input id="confirmation" name="confirmation" type="password" autocomplete="new-password" minlength="14" maxlength="128" [(ngModel)]="confirmation" required>
 @if(error()){<p role="alert">{{error()}}</p>}<button type="submit" [disabled]="busy()">Replace password</button><button type="button" (click)="cancelReplacement()">Cancel</button></form></main>
}@else{
 <main class="auth-screen"><form class="auth-card" (ngSubmit)="login()"><h1>MerchantOS POS</h1><p>Sign in with your cashier account.</p>
 <label for="username">Username</label><input id="username" name="username" autocomplete="username" maxlength="80" [(ngModel)]="username" required>
 <label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="128" [(ngModel)]="password" required>
 @if(error()){<p role="alert">{{error()}}</p>}<button type="submit" [disabled]="busy()">Sign In</button></form></main>
}`,styles:[`.auth-screen{min-height:100vh;display:grid;place-items:center;background:#f8fafc;padding:24px}.auth-card{width:100%;max-width:380px;display:grid;gap:12px;background:white;padding:28px;border:1px solid #e2e8f0;border-radius:16px}.auth-card h1{margin:0;font-size:24px}.auth-card p{margin:0 0 8px;color:#64748b}.auth-card input{min-height:44px;border:1px solid #cbd5e1;border-radius:8px;padding:8px}.auth-card button,.session-bar button{min-height:44px;border:0;border-radius:8px;background:#059669;color:white;padding:8px 16px}.session-bar{display:flex;align-items:center;justify-content:flex-end;gap:16px;padding:4px 16px;background:#f8fafc;font-size:12px}.auth-card [role=alert]{color:#b91c1c}@media print{.session-bar{display:none}}`]})
export class AppComponent {
 readonly auth=inject(AuthService); username='';password='';replacement='';confirmation='';readonly error=signal('');readonly busy=signal(false);
 constructor(){this.auth.load();}
 login(){this.busy.set(true);this.error.set('');this.auth.login(this.username,this.password).subscribe({next:()=>{this.password='';this.busy.set(false);},error:()=>{this.password='';this.busy.set(false);this.error.set('Unable to sign in. Check your credentials or try again later.');}});}
 replacePassword(){if(this.replacement!==this.confirmation){this.error.set('Passwords must match.');return;}this.busy.set(true);this.error.set('');this.auth.replacePassword(this.replacement).subscribe({next:()=>{this.replacement=this.confirmation='';this.busy.set(false);},error:()=>{this.replacement=this.confirmation='';this.busy.set(false);this.error.set('Unable to replace password. Check the policy or cancel and sign in again.');}});}
 cancelReplacement(){this.auth.cancelReplacement().subscribe({next:()=>{this.replacement=this.confirmation='';this.error.set('');},error:()=>this.error.set('Unable to cancel. Retry.')});}
 logout(){this.auth.logout().subscribe({error:()=>this.error.set('Unable to sign out. Please retry.')});}
}

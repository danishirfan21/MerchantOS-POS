import {request} from '@playwright/test';
import {writeFileSync} from 'node:fs';
export default async function setup(){const api=await request.newContext({baseURL:'http://127.0.0.1:5080'});let csrf=await (await api.get('/api/auth/csrf')).json();
 const login=await api.post('/api/auth/login',{headers:{'X-CSRF-TOKEN':csrf.token},data:{username:process.env['TEST_CASHIER_USERNAME'],password:process.env['TEST_CASHIER_PASSWORD']}});if(!login.ok())throw new Error('Cashier browser fixture sign-in failed');
 writeFileSync('/tmp/merchant-pos-state.json',JSON.stringify(await api.storageState()),{mode:0o600});await api.dispose();}

using System.Text.RegularExpressions;
using MerchantOS.Api.Security;
using Microsoft.AspNetCore.Identity;
using Npgsql;
namespace MerchantOS.Api;
public static class AccountCommand {
 public static async Task Run(WebApplication app){
  var config=app.Configuration;
  if(!config.GetValue<bool>("Operations:AllowAccountCommand"))throw new InvalidOperationException("Account commands require explicit operator authorization configuration.");
  var op=config["Account:Operation"];var name=config["Account:Username"]?.Trim().ToLowerInvariant()??"";var password=config["Account:Password"]??"";var role=config["Account:Role"]??"";
  if(!Regex.IsMatch(name,"^[a-z0-9._@-]{3,80}$")||op is not("create" or "disable" or "role" or "password" or "recover" or "revoke" or "mfa-reset" or "mfa-seed" or "restore-recover"))throw new InvalidOperationException("Supply a valid account operation and username through operator configuration.");
  if(op is "create" or "password" or "recover" or "restore-recover" && !IdentitySecurity.PasswordValid(password))throw new InvalidOperationException("A password of 14–128 characters is required through a secret file.");
  if(op is "create" or "role" && role is not("Administrator" or "Cashier"))throw new InvalidOperationException("Administrator or Cashier role required.");
  var trace=Guid.NewGuid();
  if(op is "password" or "recover" or "mfa-reset" or "restore-recover"){
   if(!Guid.TryParse(config["Operations:OperatorCase"],out trace))throw new InvalidOperationException("Recovery/reset requires an operator identity-verification case UUID.");
   if(op is "password" or "recover" or "restore-recover" && !config.GetValue<bool>("Operations:AllowRecovery"))throw new InvalidOperationException("Password recovery requires separate operator authorization.");
   if(op is "mfa-reset" or "restore-recover" && !config.GetValue<bool>("Operations:AllowMfaReset"))throw new InvalidOperationException("MFA reset requires separate operator authorization.");
   if(op=="restore-recover"&&!config.GetValue<bool>("Operations:AllowRestoreRelease"))throw new InvalidOperationException("Restored account release requires explicit reconciliation authorization.");
  }
  string? output=null;string[] codes=[];
  if(op=="mfa-seed"){
   if(!config.GetValue<bool>("Operations:AllowMfaEnrollment"))throw new InvalidOperationException("Operator enrollment requires explicit authorization and authenticator confirmation.");
   output=config["Account:RecoveryFile"]??throw new InvalidOperationException("Private, new recovery output file required.");if(!Path.IsPathFullyQualified(output)||File.Exists(output))throw new InvalidOperationException("Recovery output must be a new absolute private file.");
  }
  await using var c=await app.Services.GetRequiredService<NpgsqlDataSource>().OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();Guid id;
  if(op=="create"){
   id=Guid.NewGuid();var user=new AuthUser(id,name,role);var hash=app.Services.GetRequiredService<IPasswordHasher<AuthUser>>().HashPassword(user,password);
   await using var create=IdentitySecurity.Command(c,tx,"INSERT INTO auth_users(id,username,password_hash,role) VALUES(@id,@name,@hash,@role) ON CONFLICT(username) DO NOTHING",("id",id),("name",name),("hash",hash),("role",role));if(await create.ExecuteNonQueryAsync()!=1)throw new InvalidOperationException("Account exists; create never overwrites credentials.");
  }else{
   await using var lookup=IdentitySecurity.Command(c,tx,"SELECT id,role FROM auth_users WHERE username=@name FOR UPDATE",("name",name));await using var reader=await lookup.ExecuteReaderAsync();if(!await reader.ReadAsync())throw new InvalidOperationException("Account not found.");id=reader.GetGuid(0);var currentRole=reader.GetString(1);await reader.CloseAsync();var user=new AuthUser(id,name,currentRole);
   if(op=="disable")await IdentitySecurity.Execute(c,tx,"UPDATE auth_users SET enabled=false WHERE id=@id",("id",id));
   if(op=="role")await IdentitySecurity.Execute(c,tx,"UPDATE auth_users SET role=@role WHERE id=@id",("role",role),("id",id));
   if(op is "password" or "recover" or "restore-recover")await IdentitySecurity.Execute(c,tx,"UPDATE auth_users SET password_hash=@hash,must_change_password=true,failures=0,locked_until=NULL WHERE id=@id",("hash",app.Services.GetRequiredService<IPasswordHasher<AuthUser>>().HashPassword(user,password)),("id",id));
   if(op is "mfa-reset" or "restore-recover")await IdentitySecurity.Execute(c,tx,"UPDATE auth_users SET mfa_enabled=false,mfa_secret=NULL,mfa_last_step=-1,mfa_failures=0,mfa_locked_until=NULL WHERE id=@id; DELETE FROM auth_recovery_codes WHERE user_id=@id",("id",id));
   if(op=="restore-recover")await IdentitySecurity.Execute(c,tx,"DELETE FROM auth_restore_blocks WHERE user_id=@id",("id",id));
   if(op=="mfa-seed")codes=await app.Services.GetRequiredService<IdentitySecurity>().OperatorEnroll(c,tx,user,config["Account:MfaSecret"]??"",config["Account:Code"]??"",config.GetValue<int?>("Account:RecoveryCount")??10);
   else await IdentitySecurity.Revoke(c,tx,id);
  }
  await IdentitySecurity.Event(c,tx,"operator_"+op!.Replace('-','_'),null,id,"success",trace.ToString("N"));await tx.CommitAsync();
  if(output is not null){using var stream=new FileStream(output,FileMode.CreateNew,FileAccess.Write,FileShare.None);if(!OperatingSystem.IsWindows())File.SetUnixFileMode(output,UnixFileMode.UserRead|UnixFileMode.UserWrite);using var writer=new StreamWriter(stream);foreach(var code in codes)await writer.WriteLineAsync(code);}
  Console.WriteLine("Operator account operation completed; no credentials or recovery material logged. Recovery changes require password replacement and preserve MFA unless separately reset.");
 }
}

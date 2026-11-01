using System.Text.RegularExpressions;
using MerchantOS.Api.Security;
using Microsoft.AspNetCore.Identity;
using Npgsql;
namespace MerchantOS.Api;
public static class AccountCommand {
 public static async Task Run(WebApplication app){
  if(!app.Configuration.GetValue<bool>("Operations:AllowAccountCommand"))throw new InvalidOperationException("Account commands require explicit operator authorization configuration.");
  var op=app.Configuration["Account:Operation"];var name=app.Configuration["Account:Username"]?.Trim().ToLowerInvariant()??"";var password=app.Configuration["Account:Password"]??"";var role=app.Configuration["Account:Role"]??"";
  if(!Regex.IsMatch(name,"^[a-z0-9._@-]{3,80}$")||op is not("create" or "disable" or "role" or "password" or "revoke"))throw new InvalidOperationException("Supply a valid account operation and username through operator configuration.");
  if(op is "create" or "password"&&password.Length is <14 or >128)throw new InvalidOperationException("A password of 14–128 characters is required through a secret file.");
  if(op is "create" or "role"&&role is not("Administrator" or "Cashier"))throw new InvalidOperationException("Administrator or Cashier role required.");
  await using var c=await app.Services.GetRequiredService<NpgsqlDataSource>().OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();
  if(op=="create"){
   var user=new AuthUser(Guid.NewGuid(),name,role);var hash=app.Services.GetRequiredService<IPasswordHasher<AuthUser>>().HashPassword(user,password);
   await using var create=new NpgsqlCommand("INSERT INTO auth_users(id,username,password_hash,role) VALUES(@id,@name,@hash,@role) ON CONFLICT(username) DO NOTHING",c,tx);create.Parameters.AddWithValue("id",user.Id);create.Parameters.AddWithValue("name",name);create.Parameters.AddWithValue("hash",hash);create.Parameters.AddWithValue("role",role);if(await create.ExecuteNonQueryAsync()!=1)throw new InvalidOperationException("Account exists; create never overwrites credentials.");
  }else{
   await using var lookup=new NpgsqlCommand("SELECT id,role FROM auth_users WHERE username=@name FOR UPDATE",c,tx);lookup.Parameters.AddWithValue("name",name);await using var reader=await lookup.ExecuteReaderAsync();if(!await reader.ReadAsync())throw new InvalidOperationException("Account not found.");var id=reader.GetGuid(0);var currentRole=reader.GetString(1);await reader.CloseAsync();
   var sql=op switch{"disable"=>"UPDATE auth_users SET enabled=false WHERE id=@id","role"=>"UPDATE auth_users SET role=@role WHERE id=@id","password"=>"UPDATE auth_users SET password_hash=@hash,failures=0,locked_until=NULL WHERE id=@id",_=>"SELECT 1"};
   await using var cmd=new NpgsqlCommand(sql,c,tx);if(op!="revoke")cmd.Parameters.AddWithValue("id",id);if(op=="role")cmd.Parameters.AddWithValue("role",role);if(op=="password")cmd.Parameters.AddWithValue("hash",app.Services.GetRequiredService<IPasswordHasher<AuthUser>>().HashPassword(new(id,name,currentRole),password));await cmd.ExecuteNonQueryAsync();
   await using var revoke=new NpgsqlCommand("DELETE FROM auth_sessions WHERE user_id=@id",c,tx);revoke.Parameters.AddWithValue("id",id);await revoke.ExecuteNonQueryAsync();
  }
  await tx.CommitAsync();Console.WriteLine("Operator account operation completed; existing sessions revoked for account changes.");
 }
}

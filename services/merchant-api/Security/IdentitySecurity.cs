using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Identity;
using Npgsql;
using NpgsqlTypes;
using OtpNet;
namespace MerchantOS.Api.Security;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record FactorRequest(string? Code=null,string? RecoveryCode=null,string? NewPassword=null);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record PasswordRequest(string CurrentPassword,string NewPassword);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record RegenerateRequest(string CurrentPassword,string Code);
public sealed record LoginChallenge(Guid Id,string Username,string Step,DateTimeOffset ExpiresAt,bool MustChangePassword);
public sealed record SessionGrant(AuthUser User,string Reference,DateTimeOffset ExpiresAt);
public sealed record EnrollmentInfo(string Secret,string OtpAuthUri,DateTimeOffset ExpiresAt);
public sealed record FactorResult(SessionGrant? Grant,string[] RecoveryCodes,int Status=200);

public sealed class IdentitySecurity(NpgsqlDataSource db,IDataProtectionProvider dp,IPasswordHasher<AuthUser> hasher) {
 public const string ChallengeCookie="MerchantOS.Pos.Challenge";
 public static string Hash(string value)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
 public static bool PasswordValid(string? value)=>value is {Length:>=14 and <=128} && !string.IsNullOrWhiteSpace(value);
 public static bool VerifyTotp(byte[] secret,string? code,DateTime utc,out long step){
  step=-1;if(code is not {Length:6}||code.Any(c=>c<'0'||c>'9'))return false;
  var totp=new Totp(secret);var supplied=Encoding.ASCII.GetBytes(code);bool found=false;
  // Compute with the maintained RFC implementation; compare every candidate in fixed time.
  foreach(var offset in new[]{-1,0,1}){var instant=utc.AddSeconds(offset*30);var expected=Encoding.ASCII.GetBytes(totp.ComputeTotp(instant));var match=CryptographicOperations.FixedTimeEquals(expected,supplied);if(match){step=new DateTimeOffset(instant).ToUnixTimeSeconds()/30;found=true;}}
  return found;
 }
 IDataProtector Protector(Guid id,string scope)=>dp.CreateProtector("MerchantOS.Mfa.v1",id.ToString(),scope);
 public static NpgsqlCommand Command(NpgsqlConnection c,NpgsqlTransaction tx,string sql,params (string Name,object Value)[] values){var cmd=new NpgsqlCommand(sql,c,tx);foreach(var (name,value) in values)cmd.Parameters.AddWithValue(name,value);return cmd;}
 public static async Task Execute(NpgsqlConnection c,NpgsqlTransaction tx,string sql,params (string Name,object Value)[] values){await using var cmd=Command(c,tx,sql,values);await cmd.ExecuteNonQueryAsync();}
 public static async Task Event(NpgsqlConnection c,NpgsqlTransaction tx,string category,Guid? actor,Guid? target,string outcome,string correlation){
  if(!Guid.TryParse(correlation,out var trace))trace=Guid.NewGuid();
  await using var cmd=Command(c,tx,"INSERT INTO security_events(id,category,actor_id,target_id,outcome,correlation_id) VALUES(@id,@category,@actor,@target,@outcome,@trace)",("id",Guid.NewGuid()),("category",category),("outcome",outcome),("trace",trace.ToString("N")));
  cmd.Parameters.AddWithValue("actor",NpgsqlDbType.Uuid,(object?)actor??DBNull.Value);cmd.Parameters.AddWithValue("target",NpgsqlDbType.Uuid,(object?)target??DBNull.Value);await cmd.ExecuteNonQueryAsync();
 }
 public static async Task Revoke(NpgsqlConnection c,NpgsqlTransaction tx,Guid id){
  await Execute(c,tx,"UPDATE auth_users SET security_version=security_version+1 WHERE id=@id; DELETE FROM auth_sessions WHERE user_id=@id; DELETE FROM auth_challenges WHERE user_id=@id",("id",id));
 }
 public async Task<(LoginChallenge Challenge,string Reference)> Begin(NpgsqlConnection c,NpgsqlTransaction tx,AuthUser user,long version,bool enrolled,bool change,string correlation){
  var reference="MCH_"+Convert.ToHexString(RandomNumberGenerator.GetBytes(32));var hash=Hash(reference);var purpose=user.Role=="Administrator"?(enrolled?"verify":"enroll"):"password";var expiry=DateTimeOffset.UtcNow.AddMinutes(5);
  await Execute(c,tx,"DELETE FROM auth_challenges WHERE user_id=@id",("id",user.Id));
  await using var cmd=Command(c,tx,"INSERT INTO auth_challenges(id_hash,user_id,security_version,purpose,pending_secret,expires_at) VALUES(@hash,@id,@version,@purpose,@secret,@expiry)",("hash",hash),("id",user.Id),("version",version),("purpose",purpose),("expiry",expiry));
  cmd.Parameters.AddWithValue("secret",NpgsqlDbType.Bytea,purpose=="enroll"?Protector(user.Id,hash).Protect(RandomNumberGenerator.GetBytes(32)):DBNull.Value);await cmd.ExecuteNonQueryAsync();
  await Event(c,tx,"primary_authenticated",user.Id,user.Id,"restricted",correlation);return(new(user.Id,user.Username,purpose,expiry,change),reference);
 }
 public static async Task<SessionGrant> Grant(NpgsqlConnection c,NpgsqlTransaction tx,AuthUser user,long version,bool mfa,string method,string correlation){
  var reference=Convert.ToHexString(RandomNumberGenerator.GetBytes(32));var expiry=DateTimeOffset.UtcNow.AddMinutes(30);var verified=DateTimeOffset.UtcNow;
  await using var cmd=Command(c,tx,"INSERT INTO auth_sessions(id,user_id,expires_at,security_version,mfa_verified_at,mfa_method) VALUES(@ref,@id,@expiry,@version,@verified,@method)",("ref",reference),("id",user.Id),("expiry",expiry),("version",version),("method",method));
  cmd.Parameters.AddWithValue("verified",NpgsqlDbType.TimestampTz,mfa?verified:DBNull.Value);await cmd.ExecuteNonQueryAsync();
  await Event(c,tx,"authentication_succeeded",user.Id,user.Id,mfa?method:"password",correlation);return new(user with{MfaVerified=mfa,MfaVerifiedAt=mfa?verified:null},reference,expiry);
 }
 public static async Task SignIn(HttpContext context,SessionGrant grant){await context.SignInAsync(AuthSecurity.Scheme,AuthSecurity.Principal(grant.User),new AuthenticationProperties{ExpiresUtc=grant.ExpiresAt,AllowRefresh=false,Items={{"issued_session",grant.Reference}}});}
 public async Task<EnrollmentInfo?> Enrollment(string? reference){
  if(reference is null||reference.Length!=68)return null;var hash=Hash(reference);
  await using var c=await db.OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();
  await using var cmd=Command(c,tx,"UPDATE auth_challenges h SET enrollment_shown=true FROM auth_users u WHERE h.id_hash=@hash AND u.id=h.user_id AND h.purpose='enroll' AND NOT h.enrollment_shown AND h.expires_at>clock_timestamp() AND h.consumed_at IS NULL AND h.attempts<5 AND h.security_version=u.security_version AND u.enabled AND NOT u.mfa_enabled AND NOT EXISTS(SELECT 1 FROM auth_restore_blocks b WHERE b.user_id=u.id) RETURNING h.user_id,u.username,h.pending_secret,h.expires_at",("hash",hash));
  await using var reader=await cmd.ExecuteReaderAsync();if(!await reader.ReadAsync())return null;var id=reader.GetGuid(0);var name=reader.GetString(1);var secret=Protector(id,hash).Unprotect((byte[])reader[2]);var expiry=new DateTimeOffset(reader.GetDateTime(3));await reader.CloseAsync();await tx.CommitAsync();
  var encoded=Base32Encoding.ToString(secret);return new(encoded,new OtpUri(OtpType.Totp,encoded,name,"MerchantOS").ToString(),expiry);
 }
 public async Task<string[]> GenerateRecoveryCodes(NpgsqlConnection c,NpgsqlTransaction tx,Guid id,int count=10){
  var result=new string[count];for(int i=0;i<count;i++){result[i]="MRC_"+Convert.ToHexString(RandomNumberGenerator.GetBytes(32));await Execute(c,tx,"INSERT INTO auth_recovery_codes(user_id,code_hash) VALUES(@id,@hash)",("id",id),("hash",Hash(result[i])));}return result;
 }
 public async Task<FactorResult> Complete(string? reference,FactorRequest request,string correlation){
  if(reference is null||reference.Length!=68||request.Code?.Length>6||request.RecoveryCode?.Length>68||request.NewPassword?.Length>128)return new(null,[],401);
  var hash=Hash(reference);await using var c=await db.OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();
  Guid id;await using(var find=Command(c,tx,"SELECT user_id FROM auth_challenges WHERE id_hash=@hash",("hash",hash))){var value=await find.ExecuteScalarAsync();if(value is not Guid found)return new(null,[],401);id=found;}
  AuthUser user;long version,last;bool enrolled,change,enabled,locked,blocked;byte[]? active;string primaryHash;
  await using(var cmd=Command(c,tx,"SELECT id,username,role,security_version,mfa_last_step,mfa_enabled,must_change_password,enabled,coalesce(GREATEST(locked_until,mfa_locked_until)>clock_timestamp(),false),mfa_secret,EXISTS(SELECT 1 FROM auth_restore_blocks WHERE user_id=auth_users.id),password_hash FROM auth_users WHERE id=@id FOR UPDATE",("id",id))){await using var r=await cmd.ExecuteReaderAsync();if(!await r.ReadAsync())return new(null,[],401);user=new(r.GetGuid(0),r.GetString(1),r.GetString(2));version=r.GetInt64(3);last=r.GetInt64(4);enrolled=r.GetBoolean(5);change=r.GetBoolean(6);enabled=r.GetBoolean(7);locked=r.GetBoolean(8);active=r.IsDBNull(9)?null:(byte[])r[9];blocked=r.GetBoolean(10);primaryHash=r.GetString(11);}
  if(!enabled||locked||blocked)return new(null,[],401);
  string purpose;byte[]? pending;bool shown;
  await using(var cmd=Command(c,tx,"SELECT purpose,pending_secret,enrollment_shown FROM auth_challenges WHERE id_hash=@hash AND security_version=@version AND consumed_at IS NULL AND expires_at>clock_timestamp() AND attempts<5 FOR UPDATE",("hash",hash),("version",version))){await using var r=await cmd.ExecuteReaderAsync();if(!await r.ReadAsync())return new(null,[],401);purpose=r.GetString(0);pending=r.IsDBNull(1)?null:(byte[])r[1];shown=r.GetBoolean(2);}
  if(change&&(!PasswordValid(request.NewPassword)||hasher.VerifyHashedPassword(user,primaryHash,request.NewPassword!)!=PasswordVerificationResult.Failed))return new(null,[],400);
  bool valid=false;long step=-1;string method="password";
  if(purpose=="password"&&user.Role=="Cashier"&&change)valid=true;
  if(user.Role=="Administrator"&&purpose=="verify"&&enrolled&&request.RecoveryCode is {Length:68} recovery&&recovery.StartsWith("MRC_",StringComparison.Ordinal)){
   await using var redeem=Command(c,tx,"UPDATE auth_recovery_codes SET consumed_at=clock_timestamp() WHERE user_id=@id AND code_hash=@hash AND consumed_at IS NULL",("id",id),("hash",Hash(recovery)));valid=await redeem.ExecuteNonQueryAsync()==1;method="recovery";
  }else if(user.Role=="Administrator"&&((purpose=="enroll"&&!enrolled&&shown&&pending is not null)||(purpose=="verify"&&enrolled&&active is not null))){
   var secret=purpose=="enroll"?Protector(id,hash).Unprotect(pending!):Protector(id,"active").Unprotect(active!);valid=VerifyTotp(secret,request.Code,DateTime.UtcNow,out step)&&step>last;method="totp";
   if(valid&&purpose=="enroll")await Execute(c,tx,"UPDATE auth_users SET mfa_enabled=true,mfa_secret=@secret WHERE id=@id",("secret",Protector(id,"active").Protect(secret)),("id",id));
  }
  if(!valid){await Execute(c,tx,"UPDATE auth_challenges SET attempts=attempts+1 WHERE id_hash=@hash; UPDATE auth_users SET mfa_failures=mfa_failures+1,mfa_locked_until=CASE WHEN mfa_failures+1>=5 THEN clock_timestamp()+interval '5 minutes' ELSE mfa_locked_until END WHERE id=@id",("hash",hash),("id",id));await Event(c,tx,"mfa_verification",id,id,"failed",correlation);await tx.CommitAsync();return new(null,[],401);}
  if(step>=0)await Execute(c,tx,"UPDATE auth_users SET mfa_last_step=@step WHERE id=@id",("step",step),("id",id));
  if(change){await Execute(c,tx,"UPDATE auth_users SET password_hash=@password,must_change_password=false,security_version=security_version+1 WHERE id=@id; DELETE FROM auth_sessions WHERE user_id=@id",("password",hasher.HashPassword(user,request.NewPassword!)),("id",id));version++;await Event(c,tx,"temporary_password_replaced",id,id,"success",correlation);}
  await Execute(c,tx,"UPDATE auth_challenges SET consumed_at=clock_timestamp(),pending_secret=NULL WHERE id_hash=@hash; UPDATE auth_users SET failures=0,locked_until=NULL,mfa_failures=0,mfa_locked_until=NULL,last_login_at=clock_timestamp() WHERE id=@id",("hash",hash),("id",id));
  string[] codes=[];if(purpose=="enroll"){codes=await GenerateRecoveryCodes(c,tx,id);await Event(c,tx,"mfa_enrolled",id,id,"success",correlation);}
  if(method=="recovery")await Event(c,tx,"recovery_code_redeemed",id,id,"success",correlation);
  var grant=await Grant(c,tx,user,version,user.Role=="Administrator",method,correlation);await tx.CommitAsync();return new(grant,codes);
 }
 public async Task<int> ChangePassword(HttpContext context,PasswordRequest request){
  if(!PasswordValid(request.NewPassword)||request.CurrentPassword is null||request.CurrentPassword.Length>128)return 400;
  var id=Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);await using var c=await db.OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();
  await using var cmd=Command(c,tx,"SELECT username,role,password_hash FROM auth_users WHERE id=@id AND enabled AND security_version=@version AND NOT must_change_password AND NOT EXISTS(SELECT 1 FROM auth_restore_blocks WHERE user_id=@id) FOR UPDATE",("id",id),("version",long.Parse(context.User.FindFirstValue("security_version")!)));await using var r=await cmd.ExecuteReaderAsync();if(!await r.ReadAsync())return 401;var user=new AuthUser(id,r.GetString(0),r.GetString(1));var stored=r.GetString(2);await r.CloseAsync();
  if(hasher.VerifyHashedPassword(user,stored,request.NewPassword)!=PasswordVerificationResult.Failed)return 400;
  if(hasher.VerifyHashedPassword(user,stored,request.CurrentPassword)==PasswordVerificationResult.Failed){await Event(c,tx,"password_change",id,id,"failed",context.TraceIdentifier);await tx.CommitAsync();return 401;}
  if(user.Role=="Administrator"&&(!DateTimeOffset.TryParse(context.User.FindFirstValue("mfa_verified_at"),out var verified)||verified<DateTimeOffset.UtcNow.AddMinutes(-5)))return 403;
  await Execute(c,tx,"UPDATE auth_users SET password_hash=@hash,must_change_password=false WHERE id=@id",("hash",hasher.HashPassword(user,request.NewPassword)),("id",id));await Revoke(c,tx,id);await Event(c,tx,"password_changed",id,id,"success",context.TraceIdentifier);await tx.CommitAsync();await context.SignOutAsync(AuthSecurity.Scheme);return 204;
 }
 public async Task<string[]?> Regenerate(HttpContext context,RegenerateRequest request){
  if(request.CurrentPassword is null||request.CurrentPassword.Length>128)return null;var id=Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);await using var c=await db.OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();
  await using var cmd=Command(c,tx,"SELECT username,role,password_hash,mfa_secret,mfa_last_step FROM auth_users WHERE id=@id AND enabled AND mfa_enabled AND security_version=@version AND NOT must_change_password AND NOT EXISTS(SELECT 1 FROM auth_restore_blocks WHERE user_id=@id) AND (mfa_locked_until IS NULL OR mfa_locked_until<clock_timestamp()) FOR UPDATE",("id",id),("version",long.Parse(context.User.FindFirstValue("security_version")!)));await using var r=await cmd.ExecuteReaderAsync();if(!await r.ReadAsync())return null;var user=new AuthUser(id,r.GetString(0),r.GetString(1));var stored=r.GetString(2);var secret=(byte[])r[3];var last=r.GetInt64(4);await r.CloseAsync();
  long step=-1;var valid=hasher.VerifyHashedPassword(user,stored,request.CurrentPassword)!=PasswordVerificationResult.Failed&&VerifyTotp(Protector(id,"active").Unprotect(secret),request.Code,DateTime.UtcNow,out step)&&step>last;
  if(!valid){await Execute(c,tx,"UPDATE auth_users SET mfa_failures=mfa_failures+1,mfa_locked_until=CASE WHEN mfa_failures+1>=5 THEN clock_timestamp()+interval '5 minutes' ELSE mfa_locked_until END WHERE id=@id",("id",id));await Event(c,tx,"recovery_regeneration",id,id,"failed",context.TraceIdentifier);await tx.CommitAsync();return null;}
  await Execute(c,tx,"UPDATE auth_users SET mfa_last_step=@step,mfa_failures=0,mfa_locked_until=NULL WHERE id=@id; DELETE FROM auth_recovery_codes WHERE user_id=@id",("step",step),("id",id));var codes=await GenerateRecoveryCodes(c,tx,id);await Revoke(c,tx,id);await Event(c,tx,"recovery_regenerated",id,id,"success",context.TraceIdentifier);await tx.CommitAsync();await context.SignOutAsync(AuthSecurity.Scheme);return codes;
 }
 public async Task<string[]> OperatorEnroll(NpgsqlConnection c,NpgsqlTransaction tx,AuthUser user,string encoded,string code,int count){
  if(user.Role!="Administrator"||encoded.Length is <32 or >64||count is <10 or >100)throw new InvalidOperationException("Invalid controlled enrollment configuration.");
  var secret=Base32Encoding.ToBytes(encoded);if(secret.Length<20||!VerifyTotp(secret,code,DateTime.UtcNow,out var step))throw new InvalidOperationException("Enrollment requires a valid authenticator confirmation.");
  await using var cmd=Command(c,tx,"UPDATE auth_users SET mfa_enabled=true,mfa_secret=@secret,mfa_last_step=@step,mfa_failures=0,mfa_locked_until=NULL WHERE id=@id AND NOT mfa_enabled",("secret",Protector(user.Id,"active").Protect(secret)),("step",step),("id",user.Id));if(await cmd.ExecuteNonQueryAsync()!=1)throw new InvalidOperationException("Enrollment cannot replace an active factor.");
  await Revoke(c,tx,user.Id);return await GenerateRecoveryCodes(c,tx,user.Id,count);
 }
 public static void Map(WebApplication app){
  app.MapPost("/api/auth/mfa/enrollment",async(HttpContext ctx,IdentitySecurity service)=>{var info=await service.Enrollment(ctx.Request.Cookies[ChallengeCookie]);return info is null?Results.Unauthorized():Results.Ok(info);}).AllowAnonymous().RequireRateLimiting("factor");
  app.MapPost("/api/auth/mfa/complete",async(HttpContext ctx,IdentitySecurity service,FactorRequest input)=>{var result=await service.Complete(ctx.Request.Cookies[ChallengeCookie],input,ctx.TraceIdentifier);if(result.Grant is null)return Results.StatusCode(result.Status);ctx.Response.Cookies.Delete(ChallengeCookie);await SignIn(ctx,result.Grant);return Results.Ok(new{user=result.Grant.User,recoveryCodes=result.RecoveryCodes,expiresAt=result.Grant.ExpiresAt});}).AllowAnonymous().RequireRateLimiting("factor");
  app.MapPost("/api/auth/mfa/cancel",async(HttpContext ctx,NpgsqlDataSource source)=>{var reference=ctx.Request.Cookies[ChallengeCookie];if(reference is {Length:68}){await using var cmd=source.CreateCommand("DELETE FROM auth_challenges WHERE id_hash=@hash");cmd.Parameters.AddWithValue("hash",Hash(reference));await cmd.ExecuteNonQueryAsync();}ctx.Response.Cookies.Delete(ChallengeCookie);return Results.NoContent();}).AllowAnonymous().RequireRateLimiting("factor");
  app.MapPost("/api/auth/password",async(HttpContext ctx,IdentitySecurity service,PasswordRequest input)=>Results.StatusCode(await service.ChangePassword(ctx,input))).RequireAuthorization("Session").RequireRateLimiting("account");
  app.MapPost("/api/auth/recovery/regenerate",async(HttpContext ctx,IdentitySecurity service,RegenerateRequest input)=>{var codes=await service.Regenerate(ctx,input);return codes is null?Results.Unauthorized():Results.Ok(new{recoveryCodes=codes});}).RequireAuthorization("Reporting").RequireRateLimiting("account");
  app.MapGet("/api/admin/security-events",async(NpgsqlDataSource source)=>{await using var cmd=source.CreateCommand("SELECT id,created_at,category,actor_id,target_id,outcome,correlation_id FROM security_events ORDER BY created_at DESC,id DESC LIMIT 100");await using var r=await cmd.ExecuteReaderAsync();var list=new List<object>();while(await r.ReadAsync())list.Add(new{id=r.GetGuid(0),timestamp=r.GetDateTime(1),category=r.GetString(2),actorId=r.IsDBNull(3)?(Guid?)null:r.GetGuid(3),targetId=r.IsDBNull(4)?(Guid?)null:r.GetGuid(4),outcome=r.GetString(5),correlationId=r.GetString(6)});return Results.Ok(list);}).RequireAuthorization("AuditRead");
 }
}

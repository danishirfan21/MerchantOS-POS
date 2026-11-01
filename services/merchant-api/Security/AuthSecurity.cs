using System.Security.Claims;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.RateLimiting;
using Npgsql;

namespace MerchantOS.Api.Security;

public sealed record LoginRequest(string Username, string Password);
public sealed record AuthUser(Guid Id, string Username, string Role, bool MfaVerified=false, DateTimeOffset? MfaVerifiedAt=null);
public static class AuthSecurity
{
    public const string Scheme = "MerchantPOS";
    public const string Cookie = "MerchantOS.Pos.Session";
    public static ClaimsPrincipal Principal(AuthUser user) {
        var identity=new ClaimsIdentity([new(ClaimTypes.NameIdentifier,user.Id.ToString()),new(ClaimTypes.Name,user.Username),new(ClaimTypes.Role,user.Role)],Scheme);
        if(user.MfaVerified&&user.MfaVerifiedAt is {} at){identity.AddClaim(new("amr","mfa"));identity.AddClaim(new("mfa_verified_at",at.ToString("O")));}
        return new(identity);
    }
    public static bool LoopbackHttp(IConfiguration config, IWebHostEnvironment env) =>
        env.IsDevelopment() && config.GetValue<bool>("Security:AllowLoopbackHttp");
    public static void AddSecurity(this WebApplicationBuilder builder)
    {
        var localHttp = LoopbackHttp(builder.Configuration, builder.Environment);
        if (builder.Configuration.GetValue<bool>("Security:AllowLoopbackHttp") && !builder.Environment.IsDevelopment())
            throw new InvalidOperationException("Loopback HTTP is development-only.");
        builder.Services.AddSingleton(_ => NpgsqlDataSource.Create(builder.Configuration.GetConnectionString("MerchantDb")!));
        builder.Services.AddSingleton<IPasswordHasher<AuthUser>, PasswordHasher<AuthUser>>();
        builder.Services.AddSingleton<DbSessionStore>();
        builder.Services.AddSingleton<IdentitySecurity>();
        builder.Services.AddAuthentication(Scheme).AddCookie(Scheme, options => {
            options.Cookie.Name = Cookie; options.Cookie.HttpOnly = true; options.Cookie.SameSite = SameSiteMode.Strict;
            options.Cookie.SecurePolicy = localHttp ? CookieSecurePolicy.SameAsRequest : CookieSecurePolicy.Always;
            options.ExpireTimeSpan = TimeSpan.FromMinutes(30); options.SlidingExpiration = false;
            options.Events.OnRedirectToLogin = context => { context.Response.Cookies.Delete(Cookie); context.Response.StatusCode = 401; return Task.CompletedTask; };
            options.Events.OnRedirectToAccessDenied = context => { context.Response.StatusCode = 403; return Task.CompletedTask; };
        });
        builder.Services.AddOptions<CookieAuthenticationOptions>(Scheme).Configure<DbSessionStore>((o, s) => o.SessionStore = s);
        builder.Services.AddAuthorization(options => {
            // Every new endpoint must opt into an explicit policy (or justified AllowAnonymous).
            options.FallbackPolicy = new AuthorizationPolicyBuilder().RequireAssertion(_ => false).Build();
            foreach (var policy in new[] { "ProductManagement", "InventoryManagement", "AuditRead", "HistoricalReporting" }) options.AddPolicy(policy, p => p.RequireRole("Administrator"));
            options.AddPolicy("Catalog", p => p.RequireRole("Administrator", "Cashier"));
            options.AddPolicy("Reporting", p => p.RequireRole("Administrator"));
            options.AddPolicy("Checkout", p => p.RequireRole("Cashier"));
            options.AddPolicy("Session", p => p.RequireRole("Administrator", "Cashier"));
        });
        builder.Services.AddAntiforgery(options => {
            options.HeaderName = "X-CSRF-TOKEN"; options.Cookie.Name = "MerchantOS.Pos.Csrf";
            options.Cookie.HttpOnly = true; options.Cookie.SameSite = SameSiteMode.Strict;
            options.Cookie.SecurePolicy = localHttp ? CookieSecurePolicy.SameAsRequest : CookieSecurePolicy.Always;
        });
        builder.Services.AddRateLimiter(options => {
            options.RejectionStatusCode = 429;
            foreach(var name in new[]{"factor","account"})options.AddPolicy(name,context=>RateLimitPartition.GetFixedWindowLimiter(name=="account"?context.User.FindFirstValue(ClaimTypes.NameIdentifier)??"unknown":context.Connection.RemoteIpAddress?.ToString()??"unknown",_=>new FixedWindowRateLimiterOptions{PermitLimit=name=="account"?6:60,Window=TimeSpan.FromMinutes(1),QueueLimit=0}));
            options.AddPolicy("login", context => RateLimitPartition.GetFixedWindowLimiter(
                context.Connection.RemoteIpAddress?.ToString() ?? "unknown", _ => new FixedWindowRateLimiterOptions {
                    PermitLimit = 60, Window = TimeSpan.FromMinutes(1), QueueLimit = 0
                }));
        });
    }
    public static void UseSecurity(this WebApplication app)
    {
        app.Use(async (context, next) => {
            context.Response.Headers.CacheControl = "no-store";
            context.Response.Headers["X-Content-Type-Options"] = "nosniff";
            context.Response.Headers["Referrer-Policy"] = "same-origin";
            if (!context.Request.IsHttps && context.Request.Path != "/api/health") {
                var host = Uri.TryCreate("http://" + context.Request.Host, UriKind.Absolute, out var uri) && uri.IsLoopback;
                if (!LoopbackHttp(app.Configuration, app.Environment) || !host || context.Connection.RemoteIpAddress is not { } ip || !System.Net.IPAddress.IsLoopback(ip)) {
                    context.Response.StatusCode = 400; return;
                }
            }
            await next();
        });
        app.UseAuthentication(); app.UseAuthorization(); app.UseRateLimiter();
        app.Use(async (context, next) => {
            if (HttpMethods.IsPost(context.Request.Method) || HttpMethods.IsPut(context.Request.Method) || HttpMethods.IsDelete(context.Request.Method) || HttpMethods.IsPatch(context.Request.Method)) {
                try { await context.RequestServices.GetRequiredService<IAntiforgery>().ValidateRequestAsync(context); }
                catch (AntiforgeryValidationException) { context.Response.StatusCode = 400; return; }
            }
            await next();
        });
    }
    public static void MapSecurity(this WebApplication app)
    {
        app.MapGet("/api/auth/csrf", (HttpContext context, IAntiforgery antiforgery) =>
            Results.Ok(new { token = antiforgery.GetAndStoreTokens(context).RequestToken })).AllowAnonymous();
        app.MapPost("/api/auth/login", async (LoginRequest input, HttpContext context, NpgsqlDataSource db, IPasswordHasher<AuthUser> hasher, IdentitySecurity identity) => {
            if (context.Request.Cookies.ContainsKey(Cookie)) { await context.SignOutAsync(Scheme); return Results.Conflict(new { message = "Session cleared. Please sign in again." }); }
            if (input.Username is null || input.Password is null || input.Username.Length > 80 || input.Password.Length > 128)
                return Results.Unauthorized();
            await using var connection = await db.OpenConnectionAsync(context.RequestAborted);
            await using var tx = await connection.BeginTransactionAsync(context.RequestAborted);
            await using var cmd = new NpgsqlCommand("SELECT id,username,role,password_hash,enabled,failures,GREATEST(locked_until,mfa_locked_until),mfa_enabled,must_change_password,security_version,EXISTS(SELECT 1 FROM auth_restore_blocks WHERE user_id=auth_users.id) FROM auth_users WHERE username=@name FOR UPDATE", connection, tx);
            cmd.Parameters.AddWithValue("name", input.Username.Trim().ToLowerInvariant());
            await using var reader = await cmd.ExecuteReaderAsync(context.RequestAborted);
            AuthUser? user = null; string hash = DummyHash; bool enabled = false, locked = false; int failures = 0; bool enrolled=false,change=false,blocked=false;long version=1;
            if (await reader.ReadAsync(context.RequestAborted)) {
                user = new(reader.GetGuid(0), reader.GetString(1), reader.GetString(2)); hash = reader.GetString(3);
                enabled = reader.GetBoolean(4); failures = reader.GetInt32(5);
                locked = !reader.IsDBNull(6) && reader.GetDateTime(6) > DateTime.UtcNow; enrolled=reader.GetBoolean(7);change=reader.GetBoolean(8);version=reader.GetInt64(9);blocked=reader.GetBoolean(10);
            }
            await reader.CloseAsync();
            var result = hasher.VerifyHashedPassword(user ?? DummyUser, hash, input.Password);
            if (user is null || !enabled || locked || blocked || result == PasswordVerificationResult.Failed) {
                if (user is not null && !locked) {
                    await using var failed = new NpgsqlCommand("UPDATE auth_users SET failures=@fail,locked_until=CASE WHEN @fail>=5 THEN now()+interval '5 minutes' ELSE NULL END WHERE id=@id", connection, tx);
                    failed.Parameters.AddWithValue("fail", failures + 1); failed.Parameters.AddWithValue("id", user.Id); await failed.ExecuteNonQueryAsync();
                }
                await IdentitySecurity.Event(connection,tx,"primary_authentication",null,user?.Id,"failed",context.TraceIdentifier);await tx.CommitAsync(); return Results.Unauthorized();
            }
            await using var success = new NpgsqlCommand("UPDATE auth_users SET failures=0,locked_until=NULL,last_login_at=now(),password_hash=@hash WHERE id=@id", connection, tx);
            success.Parameters.AddWithValue("hash", result == PasswordVerificationResult.SuccessRehashNeeded ? hasher.HashPassword(user, input.Password) : hash);
            success.Parameters.AddWithValue("id", user.Id); await success.ExecuteNonQueryAsync();
            if(user.Role=="Administrator"||change){
                var pending=await identity.Begin(connection,tx,user,version,enrolled,change,context.TraceIdentifier);await tx.CommitAsync();
                context.Response.Cookies.Append(IdentitySecurity.ChallengeCookie,pending.Reference,new CookieOptions{HttpOnly=true,Secure=!LoopbackHttp(context.RequestServices.GetRequiredService<IConfiguration>(),context.RequestServices.GetRequiredService<IWebHostEnvironment>()),SameSite=SameSiteMode.Strict,Path="/",Expires=pending.Challenge.ExpiresAt,IsEssential=true});
                return Results.Json(pending.Challenge,statusCode:202);
            }
            var grant=await IdentitySecurity.Grant(connection,tx,user,version,false,"password",context.TraceIdentifier);await tx.CommitAsync();await IdentitySecurity.SignIn(context,grant);return Results.Ok(user);
        }).AllowAnonymous().RequireRateLimiting("login");
        app.MapGet("/api/auth/me", (HttpContext context) => Results.Ok(new AuthUser(
            Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!), context.User.Identity!.Name!, context.User.FindFirstValue(ClaimTypes.Role)!,context.User.HasClaim("amr","mfa"),DateTimeOffset.TryParse(context.User.FindFirstValue("mfa_verified_at"),out var at)?at:null)))
            .RequireAuthorization("Session");
        app.MapPost("/api/auth/logout", async (HttpContext context,NpgsqlDataSource source) => {await using var c=await source.OpenConnectionAsync();await using var tx=await c.BeginTransactionAsync();var id=Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);await IdentitySecurity.Event(c,tx,"session_logout",id,id,"success",context.TraceIdentifier);await tx.CommitAsync();await context.SignOutAsync(Scheme);return Results.NoContent();}).RequireAuthorization("Session");
        IdentitySecurity.Map(app);
    }
    private static readonly AuthUser DummyUser = new(Guid.Empty, "dummy", "Cashier");
    private static readonly string DummyHash = new PasswordHasher<AuthUser>().HashPassword(DummyUser, Convert.ToHexString(RandomNumberGenerator.GetBytes(32)));
    public static async Task Bootstrap(WebApplication app)
    {
        if (!app.Environment.IsDevelopment()) throw new InvalidOperationException("Account bootstrap is development-only.");
        var username = app.Configuration["Bootstrap:Username"]?.Trim().ToLowerInvariant() ?? "";
        var password = app.Configuration["Bootstrap:Password"] ?? ""; var role = app.Configuration["Bootstrap:Role"] ?? "";
        if (!Regex.IsMatch(username, "^[a-z0-9._@-]{3,80}$") || password.Length is < 14 or > 128 || role is not ("Administrator" or "Cashier"))
            throw new InvalidOperationException("Supply valid bootstrap username, role and a password of 14–128 characters through environment configuration.");
        var user = new AuthUser(Guid.NewGuid(), username, role);
        var hash = app.Services.GetRequiredService<IPasswordHasher<AuthUser>>().HashPassword(user, password);
        await using var connection = await app.Services.GetRequiredService<NpgsqlDataSource>().OpenConnectionAsync();
        await using var cmd = new NpgsqlCommand("INSERT INTO auth_users(id,username,password_hash,role) VALUES(@id,@name,@hash,@role) ON CONFLICT(username) DO NOTHING", connection);
        cmd.Parameters.AddWithValue("id", user.Id); cmd.Parameters.AddWithValue("name", user.Username); cmd.Parameters.AddWithValue("hash", hash); cmd.Parameters.AddWithValue("role", role);
        if (await cmd.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Account exists; bootstrap does not reset passwords or change roles.");
        Console.WriteLine("Development account provisioned.");
    }
}

public sealed class DbSessionStore(NpgsqlDataSource db) : ITicketStore
{
    public async Task<string> StoreAsync(AuthenticationTicket ticket) {
        if(!ticket.Properties.Items.TryGetValue("issued_session",out var key)||key is not {Length:64})throw new InvalidOperationException("Session issuance requires a committed authoritative grant.");
        await using var cmd=db.CreateCommand("SELECT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id WHERE s.id=@id AND u.id=@user AND u.enabled AND NOT u.must_change_password AND s.security_version=u.security_version AND s.expires_at>clock_timestamp() AND (u.role<>'Administrator' OR (u.mfa_enabled AND s.mfa_verified_at IS NOT NULL)) AND NOT EXISTS(SELECT 1 FROM auth_restore_blocks b WHERE b.user_id=u.id))");
        cmd.Parameters.AddWithValue("id",key);cmd.Parameters.AddWithValue("user",Guid.Parse(ticket.Principal.FindFirstValue(ClaimTypes.NameIdentifier)!));if((bool)(await cmd.ExecuteScalarAsync())!!=true)throw new InvalidOperationException("Identity changed before cookie issuance.");return key;
    }
    public Task RenewAsync(string key, AuthenticationTicket ticket) => Task.CompletedTask; // Absolute expiry; never extend a session.
    public async Task<AuthenticationTicket?> RetrieveAsync(string key) {
        await using var cmd = db.CreateCommand("SELECT u.id,u.username,u.role,s.expires_at,s.mfa_verified_at,s.security_version FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id WHERE s.id=@id AND s.expires_at>clock_timestamp() AND u.enabled AND NOT u.must_change_password AND s.security_version=u.security_version AND (u.role<>'Administrator' OR (u.mfa_enabled AND s.mfa_verified_at IS NOT NULL)) AND NOT EXISTS(SELECT 1 FROM auth_restore_blocks b WHERE b.user_id=u.id)");
        cmd.Parameters.AddWithValue("id", key); await using var reader = await cmd.ExecuteReaderAsync();
        if (!await reader.ReadAsync()) return null;
        var principal=AuthSecurity.Principal(new(reader.GetGuid(0),reader.GetString(1),reader.GetString(2),!reader.IsDBNull(4),reader.IsDBNull(4)?null:new DateTimeOffset(reader.GetDateTime(4))));
        ((ClaimsIdentity)principal.Identity!).AddClaim(new("security_version",reader.GetInt64(5).ToString()));
        return new AuthenticationTicket(principal,
            new AuthenticationProperties { ExpiresUtc = new DateTimeOffset(reader.GetDateTime(3)), AllowRefresh = false }, AuthSecurity.Scheme);
    }
    public async Task RemoveAsync(string key) { await using var cmd = db.CreateCommand("DELETE FROM auth_sessions WHERE id=@id"); cmd.Parameters.AddWithValue("id", key); await cmd.ExecuteNonQueryAsync(); }
}

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
public sealed record AuthUser(Guid Id, string Username, string Role);
public static class AuthSecurity
{
    public const string Scheme = "MerchantPOS";
    public const string Cookie = "MerchantOS.Pos.Session";
    public static ClaimsPrincipal Principal(AuthUser user) => new(new ClaimsIdentity([
        new(ClaimTypes.NameIdentifier, user.Id.ToString()), new(ClaimTypes.Name, user.Username), new(ClaimTypes.Role, user.Role)
    ], Scheme));
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
            foreach (var policy in new[] { "ProductManagement", "InventoryManagement", "AuditRead" }) options.AddPolicy(policy, p => p.RequireRole("Administrator"));
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
        app.MapPost("/api/auth/login", async (LoginRequest input, HttpContext context, NpgsqlDataSource db, IPasswordHasher<AuthUser> hasher) => {
            if (context.Request.Cookies.ContainsKey(Cookie)) { await context.SignOutAsync(Scheme); return Results.Conflict(new { message = "Session cleared. Please sign in again." }); }
            if (input.Username is null || input.Password is null || input.Username.Length > 80 || input.Password.Length > 128)
                return Results.Unauthorized();
            await using var connection = await db.OpenConnectionAsync(context.RequestAborted);
            await using var tx = await connection.BeginTransactionAsync(context.RequestAborted);
            await using var cmd = new NpgsqlCommand("SELECT id,username,role,password_hash,enabled,failures,locked_until FROM auth_users WHERE username=@name FOR UPDATE", connection, tx);
            cmd.Parameters.AddWithValue("name", input.Username.Trim().ToLowerInvariant());
            await using var reader = await cmd.ExecuteReaderAsync(context.RequestAborted);
            AuthUser? user = null; string hash = DummyHash; bool enabled = false, locked = false; int failures = 0;
            if (await reader.ReadAsync(context.RequestAborted)) {
                user = new(reader.GetGuid(0), reader.GetString(1), reader.GetString(2)); hash = reader.GetString(3);
                enabled = reader.GetBoolean(4); failures = reader.GetInt32(5);
                locked = !reader.IsDBNull(6) && reader.GetDateTime(6) > DateTime.UtcNow;
            }
            await reader.CloseAsync();
            var result = hasher.VerifyHashedPassword(user ?? DummyUser, hash, input.Password);
            if (user is null || !enabled || locked || result == PasswordVerificationResult.Failed) {
                if (user is not null && !locked) {
                    await using var failed = new NpgsqlCommand("UPDATE auth_users SET failures=@fail,locked_until=CASE WHEN @fail>=5 THEN now()+interval '5 minutes' ELSE NULL END WHERE id=@id", connection, tx);
                    failed.Parameters.AddWithValue("fail", failures + 1); failed.Parameters.AddWithValue("id", user.Id); await failed.ExecuteNonQueryAsync();
                }
                await tx.CommitAsync(); return Results.Unauthorized();
            }
            await using var success = new NpgsqlCommand("UPDATE auth_users SET failures=0,locked_until=NULL,last_login_at=now(),password_hash=@hash WHERE id=@id", connection, tx);
            success.Parameters.AddWithValue("hash", result == PasswordVerificationResult.SuccessRehashNeeded ? hasher.HashPassword(user, input.Password) : hash);
            success.Parameters.AddWithValue("id", user.Id); await success.ExecuteNonQueryAsync(); await tx.CommitAsync();
            await context.SignOutAsync(Scheme); // Revoke the prior session before issuing a fresh ticket.
            await context.SignInAsync(Scheme, Principal(user), new AuthenticationProperties { IsPersistent = false, ExpiresUtc = DateTimeOffset.UtcNow.AddMinutes(30), AllowRefresh = false });
            return Results.Ok(user);
        }).AllowAnonymous().RequireRateLimiting("login");
        app.MapGet("/api/auth/me", (HttpContext context) => Results.Ok(new AuthUser(
            Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!), context.User.Identity!.Name!, context.User.FindFirstValue(ClaimTypes.Role)!)))
            .RequireAuthorization("Session");
        app.MapPost("/api/auth/logout", async (HttpContext context) => { await context.SignOutAsync(Scheme); return Results.NoContent(); }).RequireAuthorization("Session");
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
        var key = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
        await using var cmd = db.CreateCommand("DELETE FROM auth_sessions WHERE expires_at<=now(); INSERT INTO auth_sessions(id,user_id,expires_at) VALUES(@id,@user,@expiry)");
        cmd.Parameters.AddWithValue("id", key); cmd.Parameters.AddWithValue("user", Guid.Parse(ticket.Principal.FindFirstValue(ClaimTypes.NameIdentifier)!));
        cmd.Parameters.AddWithValue("expiry", ticket.Properties.ExpiresUtc!.Value); await cmd.ExecuteNonQueryAsync(); return key;
    }
    public Task RenewAsync(string key, AuthenticationTicket ticket) => Task.CompletedTask; // Absolute expiry; never extend a session.
    public async Task<AuthenticationTicket?> RetrieveAsync(string key) {
        await using var cmd = db.CreateCommand("SELECT u.id,u.username,u.role,s.expires_at FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id WHERE s.id=@id AND s.expires_at>now() AND u.enabled");
        cmd.Parameters.AddWithValue("id", key); await using var reader = await cmd.ExecuteReaderAsync();
        if (!await reader.ReadAsync()) return null;
        return new AuthenticationTicket(AuthSecurity.Principal(new(reader.GetGuid(0), reader.GetString(1), reader.GetString(2))),
            new AuthenticationProperties { ExpiresUtc = new DateTimeOffset(reader.GetDateTime(3)), AllowRefresh = false }, AuthSecurity.Scheme);
    }
    public async Task RemoveAsync(string key) { await using var cmd = db.CreateCommand("DELETE FROM auth_sessions WHERE id=@id"); cmd.Parameters.AddWithValue("id", key); await cmd.ExecuteNonQueryAsync(); }
}

using MerchantOS.Api;
using MerchantOS.Operations;
using MerchantOS.Api.Security;
using MerchantOS.Api.Contracts;
using MerchantOS.Api.Data;
using MerchantOS.Api.Domain;
using Microsoft.EntityFrameworkCore;

if(args.Contains("--healthcheck")){Environment.ExitCode=await OperationalSecurity.HealthProbe("/api/health/ready");return;}
var builder = WebApplication.CreateBuilder(args);
OperationalSecurity.Configure(builder,"POS");
builder.Services.AddHostedService<SessionMaintenance>();
var connectionString = builder.Configuration.GetConnectionString("MerchantDb")
    ?? throw new InvalidOperationException("ConnectionStrings:MerchantDb must be configured.");

builder.Services.AddDbContext<MerchantDbContext>(options => options.UseNpgsql(connectionString));
builder.AddSecurity();
var app = builder.Build();
OperationalSecurity.InitializeKeys(app,args);
if(args.Contains("--rotate-keys")||args.Contains("--revoke-keys"))return;
if(args.Contains("--account")){await AccountCommand.Run(app);return;}
if (args.Contains("--bootstrap-user")) { await AuthSecurity.Bootstrap(app); return; }
app.UseOperationalBoundary();
app.UseSecurity();
app.MapSecurity();
app.MapGet("/api/health/live",()=>Results.Ok(new{status="alive"})).AllowAnonymous();
app.MapGet("/api/health/ready",async(Npgsql.NpgsqlDataSource source,CancellationToken ct)=>{
 try{await using var cmd=source.CreateCommand("SELECT to_regclass('admin_ticket_sessions') IS NOT NULL AND to_regclass('admin_audit') IS NOT NULL AND to_regclass('auth_sessions') IS NOT NULL AND to_regclass('ix_orders_chronological') IS NOT NULL");cmd.CommandTimeout=2;return (bool)(await cmd.ExecuteScalarAsync(ct))!?Results.Ok(new{status="ready"}):Results.StatusCode(503);}catch{return Results.StatusCode(503);}
}).AllowAnonymous();
app.MapGet("/api/ops/metrics",(OperationalMetrics metrics)=>Results.Ok(metrics.Snapshot())).RequireAuthorization("Reporting");

app.MapGet("/api/health", async (MerchantDbContext db, CancellationToken ct) =>
{
    try
    {
        return await db.Database.CanConnectAsync(ct)
            ? Results.Ok(new { status = "ok", database = "connected" })
            : Results.Problem("Database is unavailable", statusCode: 503);
    }
    catch (Exception ex) when (ex is not OperationCanceledException)
    {
        return Results.Problem("Database is unavailable", statusCode: 503);
    }
}).AllowAnonymous();

app.MapGet("/api/products", async (MerchantDbContext db, string? search, string? category, CancellationToken ct) =>
{
    IQueryable<ProductEntity> query = db.Products.AsNoTracking();
    if (!string.IsNullOrWhiteSpace(category))
    {
        var wanted = category.Trim();
        query = query.Where(p => p.Category == wanted);
    }
    if (!string.IsNullOrWhiteSpace(search))
    {
        var keyword = $"%{search.Trim()}%";
        query = query.Where(p => EF.Functions.ILike(p.Name, keyword)
            || EF.Functions.ILike(p.NameAr, keyword)
            || EF.Functions.ILike(p.Sku, keyword));
    }
    var products = await query.OrderBy(p => p.Name).Select(p => new ProductDto(
        p.Id, p.Sku, p.Name, p.NameAr, p.Category,
        p.PriceHalalas, p.Inventory.QuantityOnHand, p.Color, p.Icon, p.Badge)).ToListAsync(ct);
    return Results.Ok(products);
}).RequireAuthorization("Catalog");

app.MapGet("/api/products/{id}", async (string id, MerchantDbContext db, CancellationToken ct) =>
{
    var product = await db.Products.AsNoTracking()
        .Where(p => p.Id == id)
        .Select(p => new ProductDto(p.Id, p.Sku, p.Name, p.NameAr, p.Category,
            p.PriceHalalas, p.Inventory.QuantityOnHand, p.Color, p.Icon, p.Badge))
        .SingleOrDefaultAsync(ct);
    return product is null ? Results.NotFound() : Results.Ok(product);
}).RequireAuthorization("Catalog");

app.MapGet("/api/inventory/{productId}", async (string productId, MerchantDbContext db, CancellationToken ct) =>
{
    var inventory = await db.InventoryLevels.AsNoTracking()
        .Where(i => i.ProductId == productId)
        .Select(i => new { i.ProductId, Stock = i.QuantityOnHand })
        .SingleOrDefaultAsync(ct);
    return inventory is null ? Results.NotFound() : Results.Ok(inventory);
}).RequireAuthorization("Catalog");

app.MapGet("/api/categories", async (MerchantDbContext db, CancellationToken ct) =>
{
    var categoryNames = await db.Products.AsNoTracking()
        .Select(p => p.Category)
        .ToListAsync(ct);
    var categories = categoryNames.GroupBy(name => name)
        .Select(group => new CategoryDto(group.Key, group.Count()))
        .OrderBy(category => category.Name)
        .ToList();
    return Results.Ok(categories);
}).RequireAuthorization("Catalog");

app.MapCheckout();
app.MapManagement();
app.MapReporting();

// Authenticated demo; public deployment remains outside scope.
app.Run();

public partial class Program { }

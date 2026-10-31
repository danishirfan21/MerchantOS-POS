using MerchantOS.Api;
using MerchantOS.Api.Security;
using MerchantOS.Api.Contracts;
using MerchantOS.Api.Data;
using MerchantOS.Api.Domain;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
var connectionString = builder.Configuration.GetConnectionString("MerchantDb")
    ?? throw new InvalidOperationException("ConnectionStrings:MerchantDb must be configured.");

builder.Services.AddDbContext<MerchantDbContext>(options => options.UseNpgsql(connectionString));
builder.AddSecurity();
var app = builder.Build();
if (args.Contains("--bootstrap-user")) { await AuthSecurity.Bootstrap(app); return; }
app.UseSecurity();
app.MapSecurity();

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

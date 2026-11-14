using System.Text.RegularExpressions;
using System.Threading.RateLimiting;
using Npgsql;

namespace MerchantOS.Api.Storefront;

// ---------------------------------------------------------------------------------------------
// Customer-safe catalog for the MerchantOS Storefront (read-only vertical slice).
//
// This surface is deliberately separate from the staff catalog (/api/products, /api/inventory,
// /api/categories), which keeps its "Catalog" (Administrator/Cashier) policy untouched. Nothing
// here reuses staff DTOs or serializes entities: every public field is listed in the records below.
//
// It is disabled unless Storefront:Catalog:Enabled=true, and is intended only for the approved
// isolated integration environment. Public production remains NO-GO (see docs/operations/readiness.md).
// ---------------------------------------------------------------------------------------------

/// <summary>Allow-listed public category. Never the internal POS category string.</summary>
public sealed record StorefrontCategoryDto(string Slug, string Label);

/// <summary>
/// The complete public product contract. No SKU, internal product id, stock quantity, inventory
/// version, cost, badge, colour/icon or audit data is part of it.
/// <c>PriceHalalas</c> is an integer amount in halalas (SAR x 100). <c>VatTreatment</c> is
/// <c>"excluded"</c>: POS unit prices are ex-VAT and the checkout adds 15% VAT on top.
/// </summary>
public sealed record StorefrontProductDto(
    string Slug,
    string Name,
    StorefrontCategoryDto Category,
    long PriceHalalas,
    string Currency,
    string VatTreatment,
    string Availability);

public sealed record StorefrontProductListDto(IReadOnlyList<StorefrontProductDto> Items, int Page, int PageSize, int Total);

public sealed record StorefrontErrorDto(string Code, string Message);

/// <summary>
/// Explicit, temporary server-side publication mapping. The POS product reference stays private;
/// price and stock are NOT duplicated here and always come from the POS database. A later phase
/// is expected to replace this with an additive public-catalog table.
/// </summary>
public sealed record PublishedProduct(string PosProductId, string Slug, string CategorySlug, string CategoryLabel);

public static class StorefrontPublication
{
    // Selected by name; ids are never matched against the Storefront fixture ids.
    public static readonly IReadOnlyList<PublishedProduct> Products =
    [
        new("p01", "iphone-15-pro", "smartphones", "Smartphones"),
        new("p02", "galaxy-s24-ultra", "smartphones", "Smartphones"),
        new("p06", "airpods-pro-2nd-gen", "audio", "Audio"),
        new("p08", "sony-wh-1000xm5", "audio", "Audio"),
        new("p11", "apple-watch-ultra-2", "wearables", "Wearables"),
    ];
}

/// <summary>Minimal row read from the POS tables for a published product.</summary>
public sealed record CatalogRow(string ProductId, string Name, long PriceHalalas, int Quantity);

public interface IStorefrontCatalogSource
{
    Task<IReadOnlyList<CatalogRow>> ReadAsync(IReadOnlyCollection<string> productIds, CancellationToken ct);
}

/// <summary>Reads price and stock from PostgreSQL inside a READ ONLY transaction.</summary>
public sealed class NpgsqlStorefrontCatalogSource(NpgsqlDataSource source) : IStorefrontCatalogSource
{
    public async Task<IReadOnlyList<CatalogRow>> ReadAsync(IReadOnlyCollection<string> productIds, CancellationToken ct)
    {
        await using var connection = await source.OpenConnectionAsync(ct);
        await using var tx = await connection.BeginTransactionAsync(ct);
        await using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", connection, tx))
            await readOnly.ExecuteNonQueryAsync(ct);
        await using var cmd = new NpgsqlCommand(
            "SELECT p.id, p.name, p.price_halalas, i.quantity_on_hand FROM products p " +
            "JOIN inventory_levels i ON i.product_id = p.id WHERE p.id = ANY(@ids)", connection, tx);
        cmd.CommandTimeout = 5;
        cmd.Parameters.AddWithValue("ids", productIds.ToArray());
        var rows = new List<CatalogRow>();
        await using (var reader = await cmd.ExecuteReaderAsync(ct))
            while (await reader.ReadAsync(ct))
                rows.Add(new CatalogRow(reader.GetString(0), reader.GetString(1), reader.GetInt64(2), reader.GetInt32(3)));
        await tx.RollbackAsync(ct);
        return rows;
    }
}

public static partial class StorefrontCatalogEndpoints
{
    public const string RatePolicy = "storefront-catalog";
    public const int MaxSearchLength = 64;
    public const int DefaultPageSize = 12;
    public const int MaxPageSize = 50;
    public const int MaxPage = 1000;
    public const int LowStockThreshold = 5;

    [GeneratedRegex("^[a-z0-9]+(-[a-z0-9]+)*$")]
    private static partial Regex SlugPattern();

    public static bool Enabled(IConfiguration configuration) => configuration.GetValue<bool>("Storefront:Catalog:Enabled");

    /// <summary>Customer-safe availability. Exact quantities are never exposed.</summary>
    public static string Availability(int quantityOnHand) =>
        quantityOnHand <= 0 ? "out-of-stock" : quantityOnHand <= LowStockThreshold ? "low-stock" : "in-stock";

    public static StorefrontProductDto Map(PublishedProduct published, CatalogRow row) => new(
        published.Slug,
        row.Name,
        new StorefrontCategoryDto(published.CategorySlug, published.CategoryLabel),
        row.PriceHalalas,
        "SAR",
        "excluded",
        Availability(row.Quantity));

    public static bool IsValidSlug(string? value) => value is { Length: > 0 and <= 64 } && SlugPattern().IsMatch(value);

    public static void AddStorefrontCatalog(this WebApplicationBuilder builder)
    {
        if (!Enabled(builder.Configuration)) return;
        builder.Services.AddSingleton<IStorefrontCatalogSource, NpgsqlStorefrontCatalogSource>();
        // All Storefront traffic arrives from the server-side BFF, so the budget is per remote address and generous.
        var limit = Math.Clamp(builder.Configuration.GetValue("Storefront:Catalog:RateLimitPerMinute", 300), 1, 6000);
        builder.Services.AddRateLimiter(options => options.AddPolicy(RatePolicy, context =>
            RateLimitPartition.GetFixedWindowLimiter(context.Connection.RemoteIpAddress?.ToString() ?? "unknown",
                _ => new FixedWindowRateLimiterOptions { PermitLimit = limit, Window = TimeSpan.FromMinutes(1), QueueLimit = 0 })));
    }

    public static void MapStorefrontCatalog(this WebApplication app)
    {
        if (!Enabled(app.Configuration)) return;
        // Explicit anonymous policy: anonymous access applies to these two GET routes only.
        app.MapGet("/api/storefront/products", List).AllowAnonymous().RequireRateLimiting(RatePolicy);
        app.MapGet("/api/storefront/products/{slug}", Detail).AllowAnonymous().RequireRateLimiting(RatePolicy);
    }

    private static IResult Error(int status, string code, string message) =>
        Results.Json(new StorefrontErrorDto(code, message), statusCode: status);

    private static IResult Bad(string message) => Error(400, "invalid_request", message);

    private static IResult Unavailable() => Error(503, "catalog_unavailable", "The catalog is temporarily unavailable. Please try again.");

    private static bool TryInt(string? raw, int fallback, int min, int max, out int value)
    {
        value = fallback;
        if (raw is null) return true;
        return int.TryParse(raw, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out value) && value >= min && value <= max;
    }

    private static async Task<IResult> List(HttpContext context, IStorefrontCatalogSource source, ILoggerFactory logs,
        string? search, string? category, string? page, string? pageSize, CancellationToken ct)
    {
        var term = search?.Trim();
        if (term is { Length: > MaxSearchLength } || (term is not null && term.Any(char.IsControl)))
            return Bad("Search text is too long or contains invalid characters.");
        var categorySlug = category?.Trim();
        if (categorySlug is { Length: > 0 } && !IsValidSlug(categorySlug)) return Bad("Category is not valid.");
        if (!TryInt(page, 1, 1, MaxPage, out var pageNumber)) return Bad("Page must be a whole number from 1 to " + MaxPage + ".");
        if (!TryInt(pageSize, DefaultPageSize, 1, MaxPageSize, out var size)) return Bad("Page size must be a whole number from 1 to " + MaxPageSize + ".");

        IReadOnlyList<CatalogRow> rows;
        try { rows = await source.ReadAsync(StorefrontPublication.Products.Select(p => p.PosProductId).ToArray(), ct); }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logs.CreateLogger("StorefrontCatalog").LogError("Storefront catalog read failed; category {Category}", ex.GetType().Name);
            return Unavailable();
        }

        var matches = new List<StorefrontProductDto>();
        foreach (var published in StorefrontPublication.Products)
        {
            var row = rows.FirstOrDefault(r => r.ProductId == published.PosProductId);
            if (row is null) continue; // published but missing in POS: never invent an entry
            var dto = Map(published, row);
            if (!string.IsNullOrEmpty(categorySlug) && dto.Category.Slug != categorySlug) continue;
            if (!string.IsNullOrEmpty(term) && !dto.Name.Contains(term, StringComparison.OrdinalIgnoreCase)) continue;
            matches.Add(dto);
        }

        var items = matches.Skip((pageNumber - 1) * size).Take(size).ToList();
        context.Response.Headers.CacheControl = "public, max-age=30";
        return Results.Json(new StorefrontProductListDto(items, pageNumber, size, matches.Count));
    }

    private static async Task<IResult> Detail(HttpContext context, IStorefrontCatalogSource source, ILoggerFactory logs,
        string slug, CancellationToken ct)
    {
        if (!IsValidSlug(slug)) return Bad("Product reference is not valid.");
        var published = StorefrontPublication.Products.FirstOrDefault(p => p.Slug == slug);
        if (published is null) return Error(404, "not_found", "Product not found.");

        IReadOnlyList<CatalogRow> rows;
        try { rows = await source.ReadAsync([published.PosProductId], ct); }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logs.CreateLogger("StorefrontCatalog").LogError("Storefront catalog read failed; category {Category}", ex.GetType().Name);
            return Unavailable();
        }

        var row = rows.FirstOrDefault(r => r.ProductId == published.PosProductId);
        if (row is null) return Error(404, "not_found", "Product not found.");
        context.Response.Headers.CacheControl = "public, max-age=30";
        return Results.Json(Map(published, row));
    }
}

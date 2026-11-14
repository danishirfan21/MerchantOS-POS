using System.Net;
using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using MerchantOS.Api.Storefront;
using Npgsql;
using Xunit;

/// <summary>Runs only when STOREFRONT_TEST_DB points at an isolated, disposable PostgreSQL database.</summary>
public sealed class RequiresDbFactAttribute : FactAttribute
{
    public static string? ConnectionString => Environment.GetEnvironmentVariable("STOREFRONT_TEST_DB");
    public RequiresDbFactAttribute() { if (string.IsNullOrWhiteSpace(ConnectionString)) Skip = "Set STOREFRONT_TEST_DB to an isolated test database to run this test."; }
}

public sealed class StorefrontCatalogTests
{
    private sealed class FakeSource(Func<IReadOnlyCollection<string>, IReadOnlyList<CatalogRow>> read) : IStorefrontCatalogSource
    {
        public int Calls;
        public Task<IReadOnlyList<CatalogRow>> ReadAsync(IReadOnlyCollection<string> ids, CancellationToken ct) { Interlocked.Increment(ref Calls); return Task.FromResult(read(ids)); }
    }

    private static readonly IReadOnlyList<CatalogRow> Rows =
    [
        new("p01", "Phone One", 429900, 8),
        new("p02", "Phone Two", 519900, 5),
        new("p06", "Earbuds", 94900, 0),
        new("p08", "Headphones", 139900, 14),
        new("p11", "Watch", 319900, 1),
    ];

    private static FakeSource Fake() => new(ids => Rows.Where(r => ids.Contains(r.ProductId)).ToList());

    private static WebApplicationFactory<Program> App(bool enabled = true, IStorefrontCatalogSource? source = null, int? limit = null, string? db = null) =>
        new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
        {
            b.UseSetting("ConnectionStrings:MerchantDb", db ?? "Host=localhost;Database=unused;Username=unused");
            if (enabled) b.UseSetting("Storefront:Catalog:Enabled", "true");
            if (limit is { } l) b.UseSetting("Storefront:Catalog:RateLimitPerMinute", l.ToString());
            if (source is not null) b.ConfigureServices(s => { s.RemoveAll<IStorefrontCatalogSource>(); s.AddSingleton(source); });
        });

    private static HttpClient Client(WebApplicationFactory<Program> app) => app.CreateClient(new() { BaseAddress = new Uri("https://localhost") });

    private static async Task<JsonElement> Json(HttpResponseMessage response) => JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.Clone();

    [Fact]
    public async Task DisabledByDefaultSoRoutesDoNotExist()
    {
        using var app = App(enabled: false, source: Fake());
        using var client = Client(app);
        // Unmapped routes fall under the deny-by-default fallback policy (401), never the catalog.
        foreach (var path in new[] { "/api/storefront/products", "/api/storefront/products/iphone-15-pro" })
        {
            var response = await client.GetAsync(path);
            Assert.True(response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.NotFound, "Got " + response.StatusCode);
        }
    }

    [Fact]
    public async Task AnonymousListReturnsOnlyAllowListedFields()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var response = await client.GetAsync("/api/storefront/products");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await Json(response);
        Assert.Equal(new[] { "items", "page", "pageSize", "total" }, body.EnumerateObject().Select(p => p.Name).OrderBy(n => n).ToArray());
        Assert.Equal(5, body.GetProperty("total").GetInt32());
        foreach (var item in body.GetProperty("items").EnumerateArray())
        {
            Assert.Equal(new[] { "availability", "category", "currency", "name", "priceHalalas", "slug", "vatTreatment" },
                item.EnumerateObject().Select(p => p.Name).OrderBy(n => n).ToArray());
            Assert.Equal(new[] { "label", "slug" }, item.GetProperty("category").EnumerateObject().Select(p => p.Name).OrderBy(n => n).ToArray());
            Assert.Equal("SAR", item.GetProperty("currency").GetString());
            Assert.Equal("excluded", item.GetProperty("vatTreatment").GetString());
        }
    }

    [Fact]
    public async Task ResponsesNeverContainInternalIdentifiersOrQuantities()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var text = await (await client.GetAsync("/api/storefront/products")).Content.ReadAsStringAsync();
        foreach (var forbidden in new[] { "\"id\"", "\"sku\"", "\"stock\"", "\"quantity", "\"version\"", "\"nameAr\"", "\"badge\"", "p01", "p06", "p11" })
            Assert.DoesNotContain(forbidden, text);
    }

    [Fact]
    public async Task PricesAreIntegerHalalasFromTheSource()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var detail = await Json(await client.GetAsync("/api/storefront/products/iphone-15-pro"));
        Assert.Equal(JsonValueKind.Number, detail.GetProperty("priceHalalas").ValueKind);
        Assert.Equal(429900L, detail.GetProperty("priceHalalas").GetInt64());
        Assert.Equal("Phone One", detail.GetProperty("name").GetString());
    }

    [Theory]
    [InlineData(-5, "out-of-stock")]
    [InlineData(0, "out-of-stock")]
    [InlineData(1, "low-stock")]
    [InlineData(5, "low-stock")]
    [InlineData(6, "in-stock")]
    [InlineData(1000, "in-stock")]
    public void AvailabilityMapping(int quantity, string expected) => Assert.Equal(expected, StorefrontCatalogEndpoints.Availability(quantity));

    [Fact]
    public async Task AvailabilityComesFromSourceQuantities()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var items = (await Json(await client.GetAsync("/api/storefront/products"))).GetProperty("items").EnumerateArray()
            .ToDictionary(i => i.GetProperty("slug").GetString()!, i => i.GetProperty("availability").GetString());
        Assert.Equal("in-stock", items["iphone-15-pro"]);
        Assert.Equal("low-stock", items["galaxy-s24-ultra"]);
        Assert.Equal("out-of-stock", items["airpods-pro-2nd-gen"]);
        Assert.Equal("in-stock", items["sony-wh-1000xm5"]);
        Assert.Equal("low-stock", items["apple-watch-ultra-2"]);
    }

    [Fact]
    public async Task PublicSlugResolutionAndUnknownSlugs()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/storefront/products/sony-wh-1000xm5")).StatusCode);
        var missing = await client.GetAsync("/api/storefront/products/not-published");
        Assert.Equal(HttpStatusCode.NotFound, missing.StatusCode);
        Assert.Equal("not_found", (await Json(missing)).GetProperty("code").GetString());
        // Internal POS ids and SKUs are not slugs.
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/storefront/products/p01")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/storefront/products/ph-ap-15p")).StatusCode);
    }

    [Theory]
    [InlineData("UPPER")]
    [InlineData("has_underscore")]
    [InlineData("-leading")]
    [InlineData("trailing-")]
    [InlineData("a--b")]
    [InlineData("a%20b")]
    public async Task MalformedSlugsAreRejected(string slug)
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var response = await client.GetAsync("/api/storefront/products/" + slug);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("invalid_request", (await Json(response)).GetProperty("code").GetString());
    }

    [Fact]
    public async Task OverlongSlugIsRejected()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/api/storefront/products/" + new string('a', 65))).StatusCode);
    }

    [Theory]
    [InlineData("pageSize=0")]
    [InlineData("pageSize=51")]
    [InlineData("pageSize=-1")]
    [InlineData("pageSize=abc")]
    [InlineData("pageSize=1.5")]
    [InlineData("page=0")]
    [InlineData("page=1001")]
    [InlineData("page=x")]
    [InlineData("category=Bad_Cat")]
    public async Task InvalidQueryIsRejectedWithConsistentError(string query)
    {
        var source = Fake();
        using var app = App(source: source);
        using var client = Client(app);
        var response = await client.GetAsync("/api/storefront/products?" + query);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        var body = await Json(response);
        Assert.Equal("invalid_request", body.GetProperty("code").GetString());
        Assert.Equal(0, source.Calls);
    }

    [Fact]
    public async Task PaginationIsBoundedAndStable()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var page2 = await Json(await client.GetAsync("/api/storefront/products?page=2&pageSize=2"));
        Assert.Equal(2, page2.GetProperty("page").GetInt32());
        Assert.Equal(2, page2.GetProperty("pageSize").GetInt32());
        Assert.Equal(5, page2.GetProperty("total").GetInt32());
        Assert.Equal(new[] { "airpods-pro-2nd-gen", "sony-wh-1000xm5" }, page2.GetProperty("items").EnumerateArray().Select(i => i.GetProperty("slug").GetString()!).ToArray());
        var beyond = await Json(await client.GetAsync("/api/storefront/products?page=9&pageSize=50"));
        Assert.Empty(beyond.GetProperty("items").EnumerateArray());
        var defaults = await Json(await client.GetAsync("/api/storefront/products"));
        Assert.Equal(StorefrontCatalogEndpoints.DefaultPageSize, defaults.GetProperty("pageSize").GetInt32());
    }

    [Fact]
    public async Task SearchIsBoundedValidatedAndCaseInsensitive()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/api/storefront/products?search=" + new string('x', 65))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/api/storefront/products?search=a%00b")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/storefront/products?search=" + new string('x', 64))).StatusCode);
        var found = await Json(await client.GetAsync("/api/storefront/products?search=PHONE"));
        Assert.Equal(3, found.GetProperty("total").GetInt32()); // Phone One, Phone Two, Headphones
        var narrowed = await Json(await client.GetAsync("/api/storefront/products?search=phone%20t"));
        Assert.Equal(1, narrowed.GetProperty("total").GetInt32());
        // LIKE metacharacters are plain text, not wildcards.
        var wildcard = await Json(await client.GetAsync("/api/storefront/products?search=%25"));
        Assert.Equal(0, wildcard.GetProperty("total").GetInt32());
        var sql = await client.GetAsync("/api/storefront/products?search=%27%3B%20DROP%20TABLE%20products%3B--");
        Assert.Equal(HttpStatusCode.OK, sql.StatusCode);
        Assert.Equal(0, (await Json(sql)).GetProperty("total").GetInt32());
    }

    [Fact]
    public async Task CategoryFilterUsesPublicSlugs()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var audio = await Json(await client.GetAsync("/api/storefront/products?category=audio"));
        Assert.Equal(2, audio.GetProperty("total").GetInt32());
        var internalName = await Json(await client.GetAsync("/api/storefront/products?category=phones"));
        Assert.Equal(0, internalName.GetProperty("total").GetInt32());
    }

    [Fact]
    public async Task PublishedProductMissingFromPosIsOmittedNotInvented()
    {
        using var app = App(source: new FakeSource(ids => Rows.Where(r => r.ProductId == "p01").ToList()));
        using var client = Client(app);
        Assert.Equal(1, (await Json(await client.GetAsync("/api/storefront/products"))).GetProperty("total").GetInt32());
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/storefront/products/sony-wh-1000xm5")).StatusCode);
    }

    [Fact]
    public async Task SourceFailureIsAConsistentSanitized503()
    {
        using var app = App(source: new FakeSource(_ => throw new InvalidOperationException("connection string Host=secret-db;Password=hunter2")));
        using var client = Client(app);
        foreach (var path in new[] { "/api/storefront/products", "/api/storefront/products/iphone-15-pro" })
        {
            var response = await client.GetAsync(path);
            Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
            var text = await response.Content.ReadAsStringAsync();
            Assert.DoesNotContain("secret-db", text);
            Assert.DoesNotContain("hunter2", text);
            Assert.DoesNotContain("InvalidOperation", text);
            Assert.Equal("catalog_unavailable", JsonDocument.Parse(text).RootElement.GetProperty("code").GetString());
            Assert.Contains("no-store", response.Headers.CacheControl!.ToString());
        }
    }

    [Fact]
    public async Task SuccessIsBrieflyCacheableAndErrorsAreNot()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var ok = await client.GetAsync("/api/storefront/products");
        Assert.True(ok.Headers.CacheControl!.Public);
        Assert.Equal(TimeSpan.FromSeconds(30), ok.Headers.CacheControl.MaxAge);
        Assert.Contains("no-store", (await client.GetAsync("/api/storefront/products?page=0")).Headers.CacheControl!.ToString());
        Assert.Contains("no-store", (await client.GetAsync("/api/storefront/products/nope")).Headers.CacheControl!.ToString());
    }

    [Fact]
    public async Task RequestsAreRateLimited()
    {
        using var app = App(source: Fake(), limit: 2);
        using var client = Client(app);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/storefront/products")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/storefront/products/iphone-15-pro")).StatusCode);
        Assert.Equal(HttpStatusCode.TooManyRequests, (await client.GetAsync("/api/storefront/products")).StatusCode);
    }

    [Theory]
    [InlineData("POST")]
    [InlineData("PUT")]
    [InlineData("PATCH")]
    [InlineData("DELETE")]
    public async Task OnlyGetIsSupported(string method)
    {
        var source = Fake();
        using var app = App(source: source);
        using var client = Client(app);
        foreach (var path in new[] { "/api/storefront/products", "/api/storefront/products/iphone-15-pro" })
        {
            var response = await client.SendAsync(new HttpRequestMessage(new HttpMethod(method), path) { Content = new StringContent("{}", System.Text.Encoding.UTF8, "application/json") });
            Assert.False(response.IsSuccessStatusCode, method + " " + path + " must not succeed");
        }
        Assert.Equal(0, source.Calls);
    }

    [Fact]
    public async Task HttpIsStillRefusedOutsideLoopbackDevelopment()
    {
        using var app = App(source: Fake());
        using var client = app.CreateClient(new() { BaseAddress = new Uri("http://localhost") });
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/api/storefront/products")).StatusCode);
    }

    [Theory]
    [InlineData("GET", "/api/products")]
    [InlineData("GET", "/api/products/p01")]
    [InlineData("GET", "/api/categories")]
    [InlineData("GET", "/api/inventory/p01")]
    [InlineData("GET", "/api/orders")]
    [InlineData("GET", "/api/orders/6f9619ff-8b86-d011-b42d-00c04fc964ff")]
    [InlineData("GET", "/api/receipts")]
    [InlineData("GET", "/api/admin/products/p01")]
    [InlineData("GET", "/api/admin/audit")]
    [InlineData("GET", "/api/admin/reports/orders")]
    [InlineData("GET", "/api/admin/reports/orders.csv")]
    [InlineData("GET", "/api/admin/reports/sales")]
    [InlineData("GET", "/api/admin/security-events")]
    [InlineData("GET", "/api/ops/metrics")]
    [InlineData("GET", "/api/ops/monitor")]
    public async Task StaffEndpointsStayProtectedWhenStorefrontCatalogIsEnabled(string method, string path)
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var response = await client.SendAsync(new HttpRequestMessage(new HttpMethod(method), path));
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("POST", "/api/checkout")]
    [InlineData("POST", "/api/admin/products/p01")]
    [InlineData("POST", "/api/admin/inventory/p01/adjustments")]
    public async Task StaffWritesAreRefusedAnonymously(string method, string path)
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        var response = await client.SendAsync(new HttpRequestMessage(new HttpMethod(method), path) { Content = new StringContent("{}", System.Text.Encoding.UTF8, "application/json") });
        Assert.True(response.StatusCode is HttpStatusCode.BadRequest or HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden, "Got " + response.StatusCode);
    }

    [Fact]
    public async Task EnablingTheCatalogMakesExactlyTwoMoreRoutesAnonymous()
    {
        static HashSet<string> Anonymous(WebApplicationFactory<Program> app)
        {
            using var client = Client(app);
            _ = client.GetAsync("/api/health/live").GetAwaiter().GetResult();
            var data = app.Services.GetRequiredService<EndpointDataSource>();
            return data.Endpoints.OfType<RouteEndpoint>()
                .Where(e => e.Metadata.GetMetadata<IAllowAnonymous>() is not null)
                .Select(e => (e.Metadata.GetMetadata<Microsoft.AspNetCore.Routing.HttpMethodMetadata>()?.HttpMethods.FirstOrDefault() ?? "ANY") + " " + e.RoutePattern.RawText)
                .ToHashSet();
        }
        using var off = App(enabled: false);
        using var on = App(enabled: true, source: Fake());
        var before = Anonymous(off);
        var after = Anonymous(on);
        Assert.Empty(before.Except(after));
        Assert.Equal(new[] { "GET /api/storefront/products", "GET /api/storefront/products/{slug}" }, after.Except(before).OrderBy(x => x).ToArray());
        Assert.DoesNotContain("GET /api/products", after);
    }

    [Fact]
    public async Task StaffPoliciesAreUnchanged()
    {
        using var app = App(source: Fake());
        using var client = Client(app);
        _ = await client.GetAsync("/api/health/live");
        var endpoints = app.Services.GetRequiredService<EndpointDataSource>().Endpoints.OfType<RouteEndpoint>().ToList();
        string? Policy(string route) => endpoints.Single(e => e.RoutePattern.RawText == route && (e.Metadata.GetMetadata<Microsoft.AspNetCore.Routing.HttpMethodMetadata>()?.HttpMethods.Contains("GET") ?? false))
            .Metadata.GetOrderedMetadata<IAuthorizeData>().Select(a => a.Policy).FirstOrDefault();
        Assert.Equal("Catalog", Policy("/api/products"));
        Assert.Equal("Catalog", Policy("/api/products/{id}"));
        Assert.Equal("Catalog", Policy("/api/inventory/{productId}"));
        Assert.Equal("Catalog", Policy("/api/categories"));
        Assert.Equal("Reporting", Policy("/api/orders"));
        Assert.Equal("Checkout", Policy("/api/receipts"));
    }

    [Fact]
    public void PublicationMapIsSmallUniqueAndHidesPosIds()
    {
        var map = StorefrontPublication.Products;
        Assert.InRange(map.Count, 3, 5);
        Assert.Equal(map.Count, map.Select(p => p.Slug).Distinct().Count());
        Assert.Equal(map.Count, map.Select(p => p.PosProductId).Distinct().Count());
        Assert.All(map, p => Assert.True(StorefrontCatalogEndpoints.IsValidSlug(p.Slug)));
        Assert.All(map, p => Assert.DoesNotContain(p.PosProductId, p.Slug));
    }

    // ---- real PostgreSQL (isolated database required) ----

    private static async Task<string> Fingerprint(string connection)
    {
        await using var source = NpgsqlDataSource.Create(connection);
        await using var cmd = source.CreateCommand(
            "SELECT concat_ws('|',(SELECT count(*) FROM orders),(SELECT count(*) FROM order_items),(SELECT count(*) FROM payments)," +
            "(SELECT count(*) FROM checkout_idempotency),(SELECT count(*) FROM admin_audit),(SELECT count(*) FROM inventory_adjustments)," +
            "(SELECT coalesce(sum(quantity_on_hand),0) FROM inventory_levels),(SELECT coalesce(sum(version),0) FROM inventory_levels)," +
            "(SELECT coalesce(sum(version),0) FROM products),(SELECT md5(string_agg(id||price_halalas::text||name,',' ORDER BY id)) FROM products))");
        return (string)(await cmd.ExecuteScalarAsync())!;
    }

    [RequiresDbFact]
    public async Task RealDatabasePricesAndStockMatchAndNothingIsMutated()
    {
        var connection = RequiresDbFactAttribute.ConnectionString!;
        var before = await Fingerprint(connection);
        using var app = App(enabled: true, db: connection);
        using var client = Client(app);

        var list = await client.GetAsync("/api/storefront/products");
        Assert.Equal(HttpStatusCode.OK, list.StatusCode);
        var text = await list.Content.ReadAsStringAsync();
        foreach (var forbidden in new[] { "PH-", "AU-", "WR-", "\"sku\"", "\"stock\"", "quantity", "\"id\"" }) Assert.DoesNotContain(forbidden, text);
        var items = JsonDocument.Parse(text).RootElement.GetProperty("items").EnumerateArray().ToList();
        Assert.Equal(StorefrontPublication.Products.Count, items.Count);

        await using var source = NpgsqlDataSource.Create(connection);
        foreach (var item in items)
        {
            var published = StorefrontPublication.Products.Single(p => p.Slug == item.GetProperty("slug").GetString());
            await using var cmd = source.CreateCommand("SELECT p.price_halalas, p.name, i.quantity_on_hand FROM products p JOIN inventory_levels i ON i.product_id=p.id WHERE p.id=@id");
            cmd.Parameters.AddWithValue("id", published.PosProductId);
            await using var reader = await cmd.ExecuteReaderAsync();
            Assert.True(await reader.ReadAsync());
            Assert.Equal(reader.GetInt64(0), item.GetProperty("priceHalalas").GetInt64());
            Assert.Equal(reader.GetString(1), item.GetProperty("name").GetString());
            Assert.Equal(StorefrontCatalogEndpoints.Availability(reader.GetInt32(2)), item.GetProperty("availability").GetString());
            var detail = await client.GetAsync("/api/storefront/products/" + published.Slug);
            Assert.Equal(HttpStatusCode.OK, detail.StatusCode);
        }
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/storefront/products/not-published")).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/products")).StatusCode);
        Assert.Equal(before, await Fingerprint(connection));
    }

    [RequiresDbFact]
    public async Task UnreachableDatabaseGivesSanitized503()
    {
        using var app = App(enabled: true, db: "Host=127.0.0.1;Port=1;Database=x;Username=x;Timeout=2;Command Timeout=2");
        using var client = Client(app);
        var response = await client.GetAsync("/api/storefront/products");
        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain("127.0.0.1", text);
        Assert.Equal("catalog_unavailable", JsonDocument.Parse(text).RootElement.GetProperty("code").GetString());
    }
}

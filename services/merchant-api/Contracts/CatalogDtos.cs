namespace MerchantOS.Api.Contracts;

public sealed record ProductDto(
    string Id, string Sku, string Name, string NameAr,
    string Category, long PriceHalalas, int Stock,
    string Color, string Icon, string? Badge);

public sealed record CategoryDto(string Name, int ProductCount);

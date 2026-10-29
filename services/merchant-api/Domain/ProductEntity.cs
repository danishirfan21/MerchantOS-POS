namespace MerchantOS.Api.Domain;

public sealed class ProductEntity
{
    public required string Id { get; set; }
    public required string Sku { get; set; }
    public required string Name { get; set; }
    public required string NameAr { get; set; }
    public required string Category { get; set; }
    public long PriceHalalas { get; set; }
    public InventoryLevelEntity Inventory { get; set; } = null!;
    public required string Color { get; set; }
    public required string Icon { get; set; }
    public string? Badge { get; set; }
}

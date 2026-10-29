namespace MerchantOS.Api.Domain;

/// <summary>One store's on-hand units per product. Read-only in milestone 2.</summary>
public sealed class InventoryLevelEntity
{
    public required string ProductId { get; set; }
    public int QuantityOnHand { get; set; }
    public ProductEntity Product { get; set; } = null!;
}

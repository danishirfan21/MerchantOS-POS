using MerchantOS.Api.Domain;
using Microsoft.EntityFrameworkCore;

namespace MerchantOS.Api.Data;

public sealed class MerchantDbContext(DbContextOptions<MerchantDbContext> options) : DbContext(options)
{
    public DbSet<ProductEntity> Products => Set<ProductEntity>();
    public DbSet<InventoryLevelEntity> InventoryLevels => Set<InventoryLevelEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        var product = modelBuilder.Entity<ProductEntity>();
        product.ToTable("products", table =>
        {
            table.HasCheckConstraint("ck_products_price", "price_halalas >= 0");
        });
        product.HasKey(p => p.Id);
        product.Property(p => p.Id).HasColumnName("id").HasMaxLength(32);
        product.Property(p => p.Sku).HasColumnName("sku").HasMaxLength(80).IsRequired();
        product.Property(p => p.Name).HasColumnName("name").HasMaxLength(240).IsRequired();
        product.Property(p => p.NameAr).HasColumnName("name_ar").HasMaxLength(240).IsRequired();
        product.Property(p => p.Category).HasColumnName("category").HasMaxLength(80).IsRequired();
        product.Property(p => p.PriceHalalas).HasColumnName("price_halalas").IsRequired();
        product.Property(p => p.Color).HasColumnName("color").HasMaxLength(40).IsRequired();
        product.Property(p => p.Icon).HasColumnName("icon").HasMaxLength(20).IsRequired();
        product.Property(p => p.Badge).HasColumnName("badge").HasMaxLength(60);
        product.HasIndex(p => p.Sku).IsUnique().HasDatabaseName("uq_products_sku");
        product.HasIndex(p => p.Category).HasDatabaseName("ix_products_category");

        var inventory = modelBuilder.Entity<InventoryLevelEntity>();
        inventory.ToTable("inventory_levels", table =>
            table.HasCheckConstraint("ck_inventory_nonnegative", "quantity_on_hand >= 0"));
        inventory.HasKey(i => i.ProductId);
        inventory.Property(i => i.ProductId).HasColumnName("product_id").HasMaxLength(32);
        inventory.Property(i => i.QuantityOnHand).HasColumnName("quantity_on_hand").IsRequired();
        inventory.HasOne(i => i.Product).WithOne(p => p.Inventory)
            .HasForeignKey<InventoryLevelEntity>(i => i.ProductId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}

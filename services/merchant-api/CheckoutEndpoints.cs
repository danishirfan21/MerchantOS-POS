using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using MerchantOS.Api.Data;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace MerchantOS.Api;

public sealed record CheckoutLine(string ProductId, int Quantity);
public sealed record CheckoutRequest(List<CheckoutLine> Items, int DiscountPercent, string PaymentMethod,
    long? CashTenderedHalalas, string IdempotencyKey, string? CardScenario);
public sealed record CheckoutResult(Guid Id, string OrderNumber, DateTime CreatedAt, string Currency, string Status,
    long SubtotalHalalas, long DiscountHalalas, long VatHalalas, long PayableHalalas,
    string PaymentMethod, long ChangeHalalas, List<ReceiptLine> Items);
public sealed record ReceiptLine(string ProductId, string Sku, string Name, int Quantity, long UnitPriceHalalas);

public static class CheckoutEndpoints
{
    public static void MapCheckout(this WebApplication app)
    {
        app.MapPost("/api/checkout", Checkout);
        app.MapGet("/api/orders", async (MerchantDbContext db, CancellationToken ct) =>
        {
            var connection = (NpgsqlConnection)db.Database.GetDbConnection();
            await connection.OpenAsync(ct);
            try
            {
                await using var cmd = new NpgsqlCommand("SELECT id, order_number, created_at, currency, status, subtotal_halalas, discount_halalas, vat_halalas, payable_halalas, payment_method, change_halalas FROM orders ORDER BY created_at DESC LIMIT 100", connection);
                await using var reader = await cmd.ExecuteReaderAsync(ct);
                var orders = new List<object>();
                while (await reader.ReadAsync(ct)) orders.Add(new { id = reader.GetGuid(0), orderNumber = reader.GetString(1), createdAt = reader.GetDateTime(2), currency = reader.GetString(3).Trim(), status = reader.GetString(4), subtotalHalalas = reader.GetInt64(5), discountHalalas = reader.GetInt64(6), vatHalalas = reader.GetInt64(7), payableHalalas = reader.GetInt64(8), paymentMethod = reader.GetString(9), changeHalalas = reader.GetInt64(10) });
                return Results.Ok(orders);
            }
            finally { await connection.CloseAsync(); }
        });
        app.MapGet("/api/orders/{id:guid}", async (Guid id, MerchantDbContext db, CancellationToken ct) =>
        {
            var connection = (NpgsqlConnection)db.Database.GetDbConnection();
            await connection.OpenAsync(ct);
            try { var receipt = await ReadReceipt(connection, null, id, ct); return receipt is null ? Results.NotFound() : Results.Ok(receipt); }
            finally { await connection.CloseAsync(); }
        });
    }

    private static async Task<IResult> Checkout(CheckoutRequest request, MerchantDbContext db, CancellationToken ct)
    {
        if (request.Items is null || request.Items.Count is < 1 or > 100 || request.Items.Any(i => string.IsNullOrWhiteSpace(i.ProductId) || i.Quantity <= 0 || i.Quantity > 1000)
            || request.Items.Select(i => i.ProductId).Distinct().Count() != request.Items.Count
            || request.DiscountPercent is not (0 or 5 or 10) || request.PaymentMethod is not ("cash" or "card")
            || string.IsNullOrWhiteSpace(request.IdempotencyKey) || request.IdempotencyKey.Length > 128
            || (request.PaymentMethod == "cash" && (request.CashTenderedHalalas is null or < 0))
            || (request.PaymentMethod == "card" && request.CardScenario is not ("success" or "decline")))
            return Results.BadRequest(new { code = "invalid_request", message = "Check items, discount, payment method and idempotency key." });

        var canonical = JsonSerializer.Serialize(new { items = request.Items.OrderBy(i => i.ProductId), request.DiscountPercent, request.PaymentMethod, request.CashTenderedHalalas, request.CardScenario });
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(canonical)));
        var connection = (NpgsqlConnection)db.Database.GetDbConnection();
        await connection.OpenAsync(ct);
        try
        {
            await using var tx = await connection.BeginTransactionAsync(IsolationLevel.ReadCommitted, ct);
            // Serialize requests sharing a key; row locks below serialize competing stock purchases.
            await using (var lockCmd = new NpgsqlCommand("SELECT pg_advisory_xact_lock(hashtext(@key))", connection, tx))
            { lockCmd.Parameters.AddWithValue("key", request.IdempotencyKey); await lockCmd.ExecuteNonQueryAsync(ct); }
            await using (var keyCmd = new NpgsqlCommand("SELECT request_hash, order_id FROM checkout_idempotency WHERE key=@key", connection, tx))
            {
                keyCmd.Parameters.AddWithValue("key", request.IdempotencyKey);
                await using var keyReader = await keyCmd.ExecuteReaderAsync(ct);
                if (await keyReader.ReadAsync(ct))
                {
                    var oldHash = keyReader.GetString(0); var orderId = keyReader.GetGuid(1);
                    await keyReader.CloseAsync();
                    if (oldHash != hash) return Results.Conflict(new { code = "idempotency_conflict", message = "This key was used for a different checkout." });
                    var existing = await ReadReceipt(connection, tx, orderId, ct);
                    return Results.Ok(existing);
                }
            }
            var lines = new List<ReceiptLine>();
            foreach (var item in request.Items.OrderBy(i => i.ProductId))
            {
                await using var cmd = new NpgsqlCommand("SELECT p.sku,p.name,p.price_halalas,i.quantity_on_hand FROM products p JOIN inventory_levels i ON i.product_id=p.id WHERE p.id=@id FOR UPDATE OF i", connection, tx);
                cmd.Parameters.AddWithValue("id", item.ProductId);
                await using var reader = await cmd.ExecuteReaderAsync(ct);
                if (!await reader.ReadAsync(ct)) return Results.NotFound(new { code = "product_unavailable", productId = item.ProductId });
                var sku = reader.GetString(0); var name = reader.GetString(1); var price = reader.GetInt64(2); var stock = reader.GetInt32(3);
                if (stock < item.Quantity) return Results.Conflict(new { code = "insufficient_stock", productId = item.ProductId, available = stock });
                lines.Add(new ReceiptLine(item.ProductId, sku, name, item.Quantity, price));
            }
            var subtotal = checked(lines.Sum(line => checked(line.UnitPriceHalalas * line.Quantity)));
            var discount = (subtotal * request.DiscountPercent + 50) / 100;
            var vat = ((subtotal - discount) * 15 + 50) / 100;
            var payable = checked(subtotal - discount + vat);
            if (request.PaymentMethod == "cash" && request.CashTenderedHalalas < payable)
                return Results.BadRequest(new { code = "insufficient_cash", payableHalalas = payable });
            if (request.PaymentMethod == "card" && request.CardScenario == "decline")
                return Results.Json(new { code = "card_declined", message = "Simulated card declined." }, statusCode: 402);
            var change = request.PaymentMethod == "cash" ? request.CashTenderedHalalas!.Value - payable : 0;
            var id = Guid.NewGuid(); var number = "MOS-" + id.ToString("N")[..12].ToUpperInvariant();
            await using (var cmd = new NpgsqlCommand("INSERT INTO orders(id,order_number,currency,status,subtotal_halalas,discount_halalas,vat_halalas,payable_halalas,payment_method,change_halalas) VALUES (@id,@number,'SAR','completed',@subtotal,@discount,@vat,@payable,@method,@change)", connection, tx))
            { cmd.Parameters.AddWithValue("id", id); cmd.Parameters.AddWithValue("number", number); cmd.Parameters.AddWithValue("subtotal", subtotal); cmd.Parameters.AddWithValue("discount", discount); cmd.Parameters.AddWithValue("vat", vat); cmd.Parameters.AddWithValue("payable", payable); cmd.Parameters.AddWithValue("method", request.PaymentMethod); cmd.Parameters.AddWithValue("change", change); await cmd.ExecuteNonQueryAsync(ct); }
            foreach (var line in lines)
            {
                await using var cmd = new NpgsqlCommand("INSERT INTO order_items(order_id,product_id,sku,name,quantity,unit_price_halalas) VALUES (@order,@product,@sku,@name,@quantity,@price); UPDATE inventory_levels SET quantity_on_hand=quantity_on_hand-@quantity WHERE product_id=@product", connection, tx);
                cmd.Parameters.AddWithValue("order", id); cmd.Parameters.AddWithValue("product", line.ProductId); cmd.Parameters.AddWithValue("sku", line.Sku); cmd.Parameters.AddWithValue("name", line.Name); cmd.Parameters.AddWithValue("quantity", line.Quantity); cmd.Parameters.AddWithValue("price", line.UnitPriceHalalas); await cmd.ExecuteNonQueryAsync(ct);
            }
            await using (var cmd = new NpgsqlCommand("INSERT INTO payments(order_id,method,result,tendered_halalas,change_halalas) VALUES (@id,@method,'completed',@tendered,@change); INSERT INTO checkout_idempotency(key,request_hash,order_id) VALUES (@key,@hash,@id)", connection, tx))
            { cmd.Parameters.AddWithValue("id", id); cmd.Parameters.AddWithValue("method", request.PaymentMethod); cmd.Parameters.AddWithValue("tendered", (object?)request.CashTenderedHalalas ?? DBNull.Value); cmd.Parameters.AddWithValue("change", change); cmd.Parameters.AddWithValue("key", request.IdempotencyKey); cmd.Parameters.AddWithValue("hash", hash); await cmd.ExecuteNonQueryAsync(ct); }
            await tx.CommitAsync(ct);
            var receipt = await ReadReceipt(connection, null, id, ct);
            return Results.Ok(receipt);
        }
        finally { await connection.CloseAsync(); }
    }

    private static async Task<CheckoutResult?> ReadReceipt(NpgsqlConnection connection, NpgsqlTransaction? tx, Guid id, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand("SELECT order_number,created_at,currency,status,subtotal_halalas,discount_halalas,vat_halalas,payable_halalas,payment_method,change_halalas FROM orders WHERE id=@id", connection, tx);
        cmd.Parameters.AddWithValue("id", id);
        await using var reader = await cmd.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct)) return null;
        var receipt = new CheckoutResult(id, reader.GetString(0), reader.GetDateTime(1), reader.GetString(2).Trim(), reader.GetString(3), reader.GetInt64(4), reader.GetInt64(5), reader.GetInt64(6), reader.GetInt64(7), reader.GetString(8), reader.GetInt64(9), []);
        await reader.CloseAsync();
        await using var itemsCmd = new NpgsqlCommand("SELECT product_id,sku,name,quantity,unit_price_halalas FROM order_items WHERE order_id=@id ORDER BY id", connection, tx);
        itemsCmd.Parameters.AddWithValue("id", id);
        await using var itemsReader = await itemsCmd.ExecuteReaderAsync(ct);
        while (await itemsReader.ReadAsync(ct)) receipt.Items.Add(new ReceiptLine(itemsReader.GetString(0), itemsReader.GetString(1), itemsReader.GetString(2), itemsReader.GetInt32(3), itemsReader.GetInt64(4)));
        return receipt;
    }
}

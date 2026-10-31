using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Npgsql;
using NpgsqlTypes;
namespace MerchantOS.Api;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record ProductUpdate(string Name, string NameAr, string Category, long PriceHalalas, long Version);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record StockAdjustment(string Operation, int Quantity, string Reason, long StockVersion, string IdempotencyKey);
public sealed record ManagedProduct(string Id,string Sku,string Name,string NameAr,string Category,long PriceHalalas,long Version,int Stock,long StockVersion);
public sealed record AdjustmentResult(Guid Id,string ProductId,int PreviousQuantity,int Delta,int NewQuantity,string Operation,string Reason,DateTime Timestamp,long StockVersion);
public static class ManagementEndpoints {
    public static readonly string[] Categories = ["Phones","Audio","Wearables","Gaming","Power","Accessories"];
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    public static void MapManagement(this WebApplication app) {
        app.MapGet("/api/admin/products/{id}",async(string id,NpgsqlDataSource db,CancellationToken ct)=> {
            await using var c=await db.OpenConnectionAsync(ct);var p=await Read(c,null,id,false,ct);
            return p is null?Results.NotFound():Results.Ok(p);
        }).RequireAuthorization("ProductManagement");
        app.MapPost("/api/admin/products/{id}",Update).RequireAuthorization("ProductManagement");
        app.MapPost("/api/admin/inventory/{id}/adjustments",Adjust).RequireAuthorization("InventoryManagement");
        app.MapGet("/api/admin/audit",History).RequireAuthorization("AuditRead");
    }
    public static Dictionary<string,string[]> Validate(ProductUpdate r) {
        var e=new Dictionary<string,string[]>();
        if(string.IsNullOrWhiteSpace(r.Name)||r.Name.Length>240)e["name"]=["Enter a name of 1–240 characters."];
        if(string.IsNullOrWhiteSpace(r.NameAr)||r.NameAr.Length>240)e["nameAr"]=["Enter an Arabic name of 1–240 characters."];
        if(!Categories.Contains(r.Category))e["category"]=["Choose an existing category."];
        if(r.PriceHalalas is <1 or >100000000)e["priceHalalas"]=["Price must be 1–100000000 integer halalas."];
        if(r.Version<1)e["version"]=["Reload the current product version."];
        return e;
    }
    public static Dictionary<string,string[]> Validate(StockAdjustment r) {
        var e=new Dictionary<string,string[]>();
        if(r.Operation is not ("restock" or "damage" or "correction"))e["operation"]=["Choose restock, damage or correction."];
        if(r.Quantity<0||r.Operation!="correction"&&r.Quantity==0)e["quantity"]=["Enter a positive quantity (zero is allowed for correction)."];
        if(string.IsNullOrWhiteSpace(r.Reason)||r.Reason.Length>500)e["reason"]=["Enter a reason of 1–500 characters."];
        if(r.StockVersion<1)e["stockVersion"]=["Reload the current stock version."];
        if(string.IsNullOrWhiteSpace(r.IdempotencyKey)||r.IdempotencyKey.Length>128)e["idempotencyKey"]=["A request key of 1–128 characters is required."];
        return e;
    }
    private static NpgsqlCommand Cmd(NpgsqlConnection c,NpgsqlTransaction? tx,string sql,params (string,object)[] parameters) {
        var cmd=new NpgsqlCommand(sql,c,tx);foreach(var (key,value) in parameters)cmd.Parameters.AddWithValue(key,value);return cmd;
    }
    private static async Task<ManagedProduct?> Read(NpgsqlConnection c,NpgsqlTransaction? tx,string id,bool locked,CancellationToken ct) {
        await using var cmd=Cmd(c,tx,"SELECT p.id,p.sku,p.name,p.name_ar,p.category,p.price_halalas,p.version,i.quantity_on_hand,i.version FROM products p JOIN inventory_levels i ON i.product_id=p.id WHERE p.id=@id"+(locked?" FOR UPDATE OF p":""),("id",id));
        await using var r=await cmd.ExecuteReaderAsync(ct);return await r.ReadAsync(ct)?new(r.GetString(0),r.GetString(1),r.GetString(2),r.GetString(3),r.GetString(4),r.GetInt64(5),r.GetInt64(6),r.GetInt32(7),r.GetInt64(8)):null;
    }
    private static object Values(ManagedProduct p)=>new {p.Name,p.NameAr,p.Category,p.PriceHalalas,p.Version};
    private static Guid Actor(HttpContext context)=>Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);
    private static async Task Audit(NpgsqlConnection c,NpgsqlTransaction tx,Guid actor,string entity,string id,string action,object before,object after,string? reason,Guid request,CancellationToken ct) {
        await using var cmd=Cmd(c,tx,"INSERT INTO admin_audit(id,actor_id,entity_type,entity_id,action,previous_values,new_values,reason,request_id) VALUES(@audit,@actor,@entity,@id,@action,@before,@after,@reason,@request)",("audit",Guid.NewGuid()),("actor",actor),("entity",entity),("id",id),("action",action),("request",request));
        cmd.Parameters.AddWithValue("before",NpgsqlDbType.Jsonb,JsonSerializer.Serialize(before,Json));cmd.Parameters.AddWithValue("after",NpgsqlDbType.Jsonb,JsonSerializer.Serialize(after,Json));cmd.Parameters.AddWithValue("reason",NpgsqlDbType.Varchar,(object?)reason??DBNull.Value);await cmd.ExecuteNonQueryAsync(ct);
    }
    private static async Task<IResult> Update(string id,ProductUpdate r,HttpContext context,NpgsqlDataSource db,CancellationToken ct) {
        var errors=Validate(r);if(errors.Count>0)return Results.ValidationProblem(errors);
        await using var c=await db.OpenConnectionAsync(ct);await using var tx=await c.BeginTransactionAsync(ct);
        var before=await Read(c,tx,id,true,ct);if(before is null)return Results.NotFound();
        if(before.Version!=r.Version)return Results.Conflict(new {code="stale_product",message="Product changed. Refresh and review before saving.",current=before});
        var after=before with {Name=r.Name.Trim(),NameAr=r.NameAr.Trim(),Category=r.Category,PriceHalalas=r.PriceHalalas,Version=checked(before.Version+1)};
        await using(var cmd=Cmd(c,tx,"UPDATE products SET name=@name,name_ar=@arabic,category=@category,price_halalas=@price,version=@version WHERE id=@id",("name",after.Name),("arabic",after.NameAr),("category",after.Category),("price",after.PriceHalalas),("version",after.Version),("id",id)))await cmd.ExecuteNonQueryAsync(ct);
        await Audit(c,tx,Actor(context),"product",id,"product.updated",Values(before),Values(after),null,Guid.NewGuid(),ct);
        await tx.CommitAsync(ct);return Results.Ok(after);
    }
    private static async Task<IResult> Adjust(string id,StockAdjustment r,HttpContext context,NpgsqlDataSource db,CancellationToken ct) {
        var errors=Validate(r);if(errors.Count>0)return Results.ValidationProblem(errors);
        var actor=Actor(context);var hash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new{id,r.Operation,r.Quantity,r.Reason,r.StockVersion},Json))));
        await using var c=await db.OpenConnectionAsync(ct);await using var tx=await c.BeginTransactionAsync(ct);
        await using(var keyLock=Cmd(c,tx,"SELECT pg_advisory_xact_lock(hashtextextended(@key,0))",("key","adjust:"+actor+":"+r.IdempotencyKey)))await keyLock.ExecuteNonQueryAsync(ct);
        await using(var key=Cmd(c,tx,"SELECT request_hash,result::text FROM inventory_adjustments WHERE actor_id=@actor AND idempotency_key=@key",("actor",actor),("key",r.IdempotencyKey))) {
            await using var reader=await key.ExecuteReaderAsync(ct);if(await reader.ReadAsync(ct))return reader.GetString(0)!=hash?Results.Conflict(new{code="idempotency_conflict",message="Request key was used with different values."}):Results.Content(reader.GetString(1),"application/json");
        }
        int stock;long version;
        await using(var cmd=Cmd(c,tx,"SELECT quantity_on_hand,version FROM inventory_levels WHERE product_id=@id FOR UPDATE",("id",id))) {
            await using var reader=await cmd.ExecuteReaderAsync(ct);if(!await reader.ReadAsync(ct))return Results.NotFound();stock=reader.GetInt32(0);version=reader.GetInt64(1);
        }
        if(version!=r.StockVersion)return Results.Conflict(new{code="stale_stock",message="Stock changed. Refresh and review the adjustment.",stock,stockVersion=version});
        long balance=r.Operation switch {"restock"=>(long)stock+r.Quantity,"damage"=>(long)stock-r.Quantity,_=>r.Quantity};
        if(balance<0||balance>int.MaxValue)return Results.ValidationProblem(new Dictionary<string,string[]>{{"quantity",["Resulting stock must be between 0 and 2147483647."]}});
        long next;
        await using(var cmd=Cmd(c,tx,"UPDATE inventory_levels SET quantity_on_hand=@stock WHERE product_id=@id RETURNING version",("stock",(int)balance),("id",id)))next=(long)(await cmd.ExecuteScalarAsync(ct))!;
        var result=new AdjustmentResult(Guid.NewGuid(),id,stock,(int)(balance-stock),(int)balance,r.Operation,r.Reason.Trim(),DateTime.UtcNow,next);
        await Audit(c,tx,actor,"inventory",id,"inventory."+r.Operation,new{stock,stockVersion=version},new{stock=result.NewQuantity,stockVersion=next},result.Reason,result.Id,ct);
        await using(var cmd=Cmd(c,tx,"INSERT INTO inventory_adjustments(id,actor_id,idempotency_key,request_hash,result) VALUES(@id,@actor,@key,@hash,@result)",("id",result.Id),("actor",actor),("key",r.IdempotencyKey),("hash",hash))) {
            cmd.Parameters.AddWithValue("result",NpgsqlDbType.Jsonb,JsonSerializer.Serialize(result,Json));await cmd.ExecuteNonQueryAsync(ct);
        }
        await tx.CommitAsync(ct);return Results.Ok(result);
    }
    private static async Task<IResult> History(NpgsqlDataSource db,CancellationToken ct,string? entityId=null,string? action=null,DateTimeOffset? from=null,DateTimeOffset? to=null,int page=1,int pageSize=10) {
        if(page is <1 or >10000||pageSize is <1 or >50||entityId?.Length>32||action is not(null or "product.updated" or "inventory.restock" or "inventory.damage" or "inventory.correction")||from>to)return Results.BadRequest(new{message="Invalid history filters."});
        await using var cmd=db.CreateCommand("SELECT a.id,a.created_at,a.actor_id,u.username,a.entity_type,a.entity_id,a.action,a.previous_values::text,a.new_values::text,a.reason,a.request_id FROM admin_audit a JOIN auth_users u ON u.id=a.actor_id WHERE (@entity IS NULL OR a.entity_id=@entity) AND (@action IS NULL OR a.action=@action) AND (@from IS NULL OR a.created_at>=@from) AND (@to IS NULL OR a.created_at<=@to) ORDER BY a.created_at DESC,a.id DESC LIMIT @limit OFFSET @offset");
        cmd.Parameters.AddWithValue("entity",NpgsqlDbType.Varchar,(object?)entityId??DBNull.Value);cmd.Parameters.AddWithValue("action",NpgsqlDbType.Varchar,(object?)action??DBNull.Value);
        cmd.Parameters.AddWithValue("from",NpgsqlDbType.TimestampTz,(object?)from?.UtcDateTime??DBNull.Value);cmd.Parameters.AddWithValue("to",NpgsqlDbType.TimestampTz,(object?)to?.UtcDateTime??DBNull.Value);cmd.Parameters.AddWithValue("limit",pageSize+1);cmd.Parameters.AddWithValue("offset",(page-1)*pageSize);
        var items=new List<object>();await using var r=await cmd.ExecuteReaderAsync(ct);
        while(await r.ReadAsync(ct))items.Add(new{id=r.GetGuid(0),timestamp=r.GetDateTime(1),actorId=r.GetGuid(2),administrator=r.GetString(3),entityType=r.GetString(4),entityId=r.GetString(5),action=r.GetString(6),previousValues=JsonSerializer.Deserialize<JsonElement>(r.GetString(7)),newValues=JsonSerializer.Deserialize<JsonElement>(r.GetString(8)),reason=r.IsDBNull(9)?null:r.GetString(9),requestId=r.GetGuid(10)});
        return Results.Ok(new{items=items.Take(pageSize),page,pageSize,hasMore=items.Count>pageSize});
    }
}

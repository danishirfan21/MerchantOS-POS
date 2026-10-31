using System.Data;
using System.Globalization;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;
namespace MerchantOS.Api;

public sealed record ReportPeriod(string Range,DateOnly? From,DateOnly? To,DateTime? StartUtc,DateTime? EndUtc,string TimeZone="Asia/Riyadh");
public sealed record ReportQuery(ReportPeriod Period,string? Search,string? PaymentMethod,string? Status,int Page,int PageSize);
public sealed record ReportOrder(Guid Id,string OrderNumber,DateTime CreatedAt,string Currency,string Status,long SubtotalHalalas,long DiscountHalalas,long VatHalalas,long PayableHalalas,string PaymentMethod,long ChangeHalalas);
public sealed record SalesSummary(long GrossHalalas,long DiscountsHalalas,long NetBeforeVatHalalas,long VatHalalas,long RevenueHalalas,long CompletedOrders,long AverageOrderHalalas);
public sealed record SalesBucket(string Label,long RevenueHalalas,long CompletedOrders);
public sealed record PaymentSales(string Method,long CompletedOrders,long RevenueHalalas,decimal RevenueShare);
public sealed record TopSale(string ProductId,string Name,long UnitsSold,long GrossHalalas);
public static class ReportingEndpoints {
 public const int ExportLimit=10000;
 public static readonly TimeZoneInfo StoreZone=TimeZoneInfo.FindSystemTimeZoneById("Asia/Riyadh");
 private const string Columns="id,order_number,created_at,currency,status,subtotal_halalas,discount_halalas,vat_halalas,payable_halalas,payment_method,change_halalas";
 private const string Where=" WHERE (@from IS NULL OR o.created_at>=@from) AND (@to IS NULL OR o.created_at<@to) AND (@search IS NULL OR strpos(lower(o.order_number),lower(@search))>0) AND (@method IS NULL OR o.payment_method=@method) AND (@status IS NULL OR o.status=@status)";
 public static void MapReporting(this WebApplication app) {
  app.MapGet("/api/admin/reports/orders",Orders).RequireAuthorization("HistoricalReporting");
  app.MapGet("/api/admin/reports/orders.csv",Export).RequireAuthorization("HistoricalReporting");
  app.MapGet("/api/admin/reports/sales",Sales).RequireAuthorization("HistoricalReporting");
 }
 public static ReportPeriod Period(string? range,string? from,string? to,bool allowAll,DateTimeOffset now) {
  range=string.IsNullOrEmpty(range)?(allowAll?"all":"today"):range;
  var today=DateOnly.FromDateTime(TimeZoneInfo.ConvertTime(now,StoreZone).DateTime);
  if(range!="custom"&&(!string.IsNullOrEmpty(from)||!string.IsNullOrEmpty(to)))throw new ArgumentException("Dates require Custom Range.");
  if(range=="all"&&allowAll)return new("all",null,null,null,null);
  var end=today;var start=today;
  switch(range) {
   case "today":break;
   case "yesterday":start=end=today.AddDays(-1);break;
   case "week":start=today.AddDays(-6);break;
   case "month":start=today.AddDays(-29);break;
   case "custom":
    if(!DateOnly.TryParseExact(from,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out start)||!DateOnly.TryParseExact(to,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out end))throw new ArgumentException("Choose valid ISO store dates.");break;
   default:throw new ArgumentException("Invalid report range.");
  }
  if(start>end||end>today||end.DayNumber-start.DayNumber>365||start.Year<2000)throw new ArgumentException("Choose a past/current range of 1–366 days, from year 2000 onwards.");
  return new(range,start,end,TimeZoneInfo.ConvertTimeToUtc(start.ToDateTime(TimeOnly.MinValue),StoreZone),TimeZoneInfo.ConvertTimeToUtc(end.AddDays(1).ToDateTime(TimeOnly.MinValue),StoreZone));
 }
 private static ReportQuery Parse(HttpContext context,bool sales=false,bool export=false) {
  var q=context.Request.Query;var allowed=sales?new[]{"range","from","to"}:export?new[]{"range","from","to","search","paymentMethod","status"}:new[]{"range","from","to","search","paymentMethod","status","page","pageSize"};
  if(q.Any(k=>!allowed.Contains(k.Key,StringComparer.OrdinalIgnoreCase)||k.Value.Count!=1))throw new ArgumentException("Unknown or duplicate report parameter.");
  var p=Period(q["range"],q["from"],q["to"],!sales,DateTimeOffset.UtcNow);
  var search=q["search"].ToString().Trim();var method=q["paymentMethod"].ToString();var status=q["status"].ToString();
  if(search.Length>120||method is not("" or "cash" or "card")||status is not("" or "completed" or "cancelled" or "failed"))throw new ArgumentException("Invalid order filter.");
  int page=1,size=20;
  if(q.ContainsKey("page")&&(!int.TryParse(q["page"],out page)||page is <1 or >100000)||q.ContainsKey("pageSize")&&(!int.TryParse(q["pageSize"],out size)||size is <1 or >100))throw new ArgumentException("Page must be 1–100000; pageSize 1–100.");
  return new(p,search.Length==0?null:search,method.Length==0?null:method,status.Length==0?null:status,page,size);
 }
 private static NpgsqlCommand Cmd(NpgsqlConnection c,NpgsqlTransaction tx,string sql,ReportQuery q) {
  var cmd=new NpgsqlCommand(sql,c,tx){CommandTimeout=10};cmd.Parameters.AddWithValue("from",NpgsqlDbType.TimestampTz,(object?)q.Period.StartUtc??DBNull.Value);cmd.Parameters.AddWithValue("to",NpgsqlDbType.TimestampTz,(object?)q.Period.EndUtc??DBNull.Value);
  cmd.Parameters.AddWithValue("search",NpgsqlDbType.Text,(object?)q.Search??DBNull.Value);cmd.Parameters.AddWithValue("method",NpgsqlDbType.Text,(object?)q.PaymentMethod??DBNull.Value);cmd.Parameters.AddWithValue("status",NpgsqlDbType.Text,(object?)q.Status??DBNull.Value);return cmd;
 }
 private static async Task<NpgsqlTransaction> Snapshot(NpgsqlConnection c,CancellationToken ct) {
  var tx=await c.BeginTransactionAsync(IsolationLevel.RepeatableRead,ct);await using var cmd=new NpgsqlCommand("SET TRANSACTION READ ONLY; SET LOCAL statement_timeout='10s'",c,tx);await cmd.ExecuteNonQueryAsync(ct);return tx;
 }
 private static IResult Invalid(ArgumentException e)=>Results.ValidationProblem(new Dictionary<string,string[]>{{"report",[e.Message]}});
 private static async Task<List<ReportOrder>> ReadOrders(NpgsqlCommand cmd,CancellationToken ct) {
  var list=new List<ReportOrder>();await using var r=await cmd.ExecuteReaderAsync(ct);
  while(await r.ReadAsync(ct))list.Add(new(r.GetGuid(0),r.GetString(1),r.GetDateTime(2),r.GetString(3).Trim(),r.GetString(4),r.GetInt64(5),r.GetInt64(6),r.GetInt64(7),r.GetInt64(8),r.GetString(9),r.GetInt64(10)));return list;
 }
 private static async Task<IResult> Orders(HttpContext context,NpgsqlDataSource source,CancellationToken ct) {
  ReportQuery q;try{q=Parse(context);}catch(ArgumentException e){return Invalid(e);}
  try{await using var c=await source.OpenConnectionAsync(ct);await using var tx=await Snapshot(c,ct);
   await using var count=Cmd(c,tx,"SELECT count(*) FROM orders o"+Where,q);var total=(long)(await count.ExecuteScalarAsync(ct))!;
   await using var cmd=Cmd(c,tx,"SELECT "+Columns+" FROM orders o"+Where+" ORDER BY created_at DESC,id DESC LIMIT @limit OFFSET @offset",q);cmd.Parameters.AddWithValue("limit",q.PageSize);cmd.Parameters.AddWithValue("offset",(q.Page-1)*q.PageSize);
   var items=await ReadOrders(cmd,ct);return Results.Ok(new{items,q.Page,q.PageSize,total,hasMore=(long)q.Page*q.PageSize<total,filter=q});
  }catch(Exception e)when(e is NpgsqlException or TimeoutException){return Results.Problem("Historical orders unavailable. Please retry.",statusCode:503);}
 }
 public static string CsvCell(string value) {
  var trimmed=value.TrimStart();if(value.Length>0&&(value[0] is '\t' or '\r' or '\n'||trimmed.Length>0&&trimmed[0] is '=' or '+' or '-' or '@'))value="'"+value;
  return "\""+value.Replace("\"","\"\"")+"\"";
 }
 private static string Money(long n)=>(n/100m).ToString("0.00",CultureInfo.InvariantCulture);
 private static async Task<IResult> Export(HttpContext context,NpgsqlDataSource source,CancellationToken ct) {
  ReportQuery q;try{q=Parse(context,export:true);}catch(ArgumentException e){return Invalid(e);}
  try{await using var c=await source.OpenConnectionAsync(ct);await using var tx=await Snapshot(c,ct);
   await using var cmd=Cmd(c,tx,"SELECT "+Columns+" FROM orders o"+Where+" ORDER BY created_at DESC,id DESC LIMIT @limit",q);cmd.Parameters.AddWithValue("limit",ExportLimit+1);var rows=await ReadOrders(cmd,ct);
   if(rows.Count>ExportLimit)return Results.Problem("Export exceeds 10000 orders. Narrow the filters.",statusCode:413);
   var csv=new StringBuilder("Order number,UTC timestamp,Store timestamp (Asia/Riyadh),Payment method,Status,Subtotal before discount,Discount,VAT,Final total including VAT,Currency\r\n");
   foreach(var o in rows){string[] cells=[o.OrderNumber,o.CreatedAt.ToUniversalTime().ToString("O"),TimeZoneInfo.ConvertTimeFromUtc(o.CreatedAt,StoreZone).ToString("yyyy-MM-dd HH:mm:ss",CultureInfo.InvariantCulture),o.PaymentMethod=="card"?"Simulated Card":o.PaymentMethod,o.Status,Money(o.SubtotalHalalas),Money(o.DiscountHalalas),Money(o.VatHalalas),Money(o.PayableHalalas),o.Currency];csv.AppendLine(string.Join(',',cells.Select(CsvCell)));}
   return Results.File(Encoding.UTF8.GetPreamble().Concat(Encoding.UTF8.GetBytes(csv.ToString())).ToArray(),"text/csv; charset=utf-8","merchantos-orders.csv");
  }catch(Exception e)when(e is NpgsqlException or TimeoutException){return Results.Problem("Export unavailable. No CSV was generated.",statusCode:503);}
 }
 public static long Average(long revenue,long count)=>count==0?0:checked((long)Math.Round((decimal)revenue/count,0,MidpointRounding.AwayFromZero));
 private static async Task<IResult> Sales(HttpContext context,NpgsqlDataSource source,CancellationToken ct) {
  ReportQuery q;try{q=Parse(context,sales:true);}catch(ArgumentException e){return Invalid(e);}
  const string completed=" FROM orders o WHERE o.created_at>=@from AND o.created_at<@to AND o.status='completed' AND o.currency='SAR'";
  try{await using var c=await source.OpenConnectionAsync(ct);await using var tx=await Snapshot(c,ct);
   long gross,discount,vat,revenue,count;
   await using(var cmd=Cmd(c,tx,"SELECT coalesce(sum(subtotal_halalas),0)::bigint,coalesce(sum(discount_halalas),0)::bigint,coalesce(sum(vat_halalas),0)::bigint,coalesce(sum(payable_halalas),0)::bigint,count(*)"+completed,q)){
    await using var r=await cmd.ExecuteReaderAsync(ct);await r.ReadAsync(ct);gross=r.GetInt64(0);discount=r.GetInt64(1);vat=r.GetInt64(2);revenue=r.GetInt64(3);count=r.GetInt64(4);
   }
   var summary=new SalesSummary(gross,discount,checked(gross-discount),vat,revenue,count,Average(revenue,count));
   var days=q.Period.To!.Value.DayNumber-q.Period.From!.Value.DayNumber+1;var bucket=days==1?"hour":days<=31?"day":"month";var format=days==1?"HH24:00":days<=31?"YYYY-MM-DD":"YYYY-MM";
   // Controlled SQL literals only; all user dates and filters remain parameters.
   var trend=new Dictionary<string,SalesBucket>();
   await using(var cmd=Cmd(c,tx,$"SELECT to_char(date_trunc('{bucket}',o.created_at AT TIME ZONE 'Asia/Riyadh'),'{format}'),sum(payable_halalas)::bigint,count(*)"+completed+" GROUP BY 1 ORDER BY 1",q)){
    await using var r=await cmd.ExecuteReaderAsync(ct);while(await r.ReadAsync(ct))trend.Add(r.GetString(0),new(r.GetString(0),r.GetInt64(1),r.GetInt64(2)));
   }
   var buckets=new List<SalesBucket>();var local=q.Period.From.Value.ToDateTime(TimeOnly.MinValue);var end=q.Period.To.Value.AddDays(1).ToDateTime(TimeOnly.MinValue);
   if(bucket=="month")local=new DateTime(local.Year,local.Month,1);
   while(local<end){var label=local.ToString(days==1?"HH':00'":days<=31?"yyyy-MM-dd":"yyyy-MM",CultureInfo.InvariantCulture);buckets.Add(trend.GetValueOrDefault(label)??new(label,0,0));local=bucket=="hour"?local.AddHours(1):bucket=="day"?local.AddDays(1):local.AddMonths(1);}
   var payments=new List<PaymentSales>();
   await using(var cmd=Cmd(c,tx,"SELECT payment_method,count(*),sum(payable_halalas)::bigint"+completed+" GROUP BY payment_method",q)){
    await using var r=await cmd.ExecuteReaderAsync(ct);while(await r.ReadAsync(ct)){var amount=r.GetInt64(2);payments.Add(new(r.GetString(0),r.GetInt64(1),amount,revenue==0?0:(decimal)amount/revenue));}
   }
   foreach(var method in new[]{"cash","card"})if(!payments.Any(p=>p.Method==method))payments.Add(new(method,0,0,0));
   var top=new List<TopSale>();
   await using(var cmd=Cmd(c,tx,"WITH selected AS (SELECT o.id,o.created_at"+completed+"), totals AS (SELECT i.product_id,sum(i.quantity)::bigint units,sum(i.quantity::bigint*i.unit_price_halalas)::bigint gross FROM order_items i JOIN selected s ON s.id=i.order_id GROUP BY i.product_id), names AS (SELECT DISTINCT ON(i.product_id) i.product_id,i.name FROM order_items i JOIN selected s ON s.id=i.order_id ORDER BY i.product_id,s.created_at DESC,s.id DESC,i.id DESC) SELECT t.product_id,n.name,t.units,t.gross FROM totals t JOIN names n USING(product_id) ORDER BY t.units DESC,t.gross DESC,t.product_id LIMIT 10",q)){
    await using var r=await cmd.ExecuteReaderAsync(ct);while(await r.ReadAsync(ct))top.Add(new(r.GetString(0),r.GetString(1),r.GetInt64(2),r.GetInt64(3)));
   }
   return Results.Ok(new{period=q.Period,summary,granularity=bucket,trend=buckets,paymentMethods=payments.OrderBy(p=>p.Method),topProducts=top});
  }catch(Exception e)when(e is NpgsqlException or TimeoutException or OverflowException){return Results.Problem("Sales report unavailable. Please retry.",statusCode:503);}
 }
}

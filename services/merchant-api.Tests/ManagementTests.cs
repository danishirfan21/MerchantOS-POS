using System.Text.Json;
using MerchantOS.Api;
using Xunit;
public sealed class ManagementTests {
 [Theory][InlineData(-1)][InlineData(0)][InlineData(100000001)]public void RejectOutOfRangePrice(long price)=>Assert.Contains("priceHalalas",ManagementEndpoints.Validate(new ProductUpdate("Valid","صالح","Phones",price,1)).Keys);
 [Fact]public void RejectUnknownFields()=>Assert.Throws<JsonException>(()=>JsonSerializer.Deserialize<ProductUpdate>("{\"name\":\"Valid\",\"sku\":\"overwrite\"}",new JsonSerializerOptions(JsonSerializerDefaults.Web)));
 [Fact]public void RejectFractionalHalalas()=>Assert.Throws<JsonException>(()=>JsonSerializer.Deserialize<ProductUpdate>("{\"priceHalalas\":1.5}",new JsonSerializerOptions(JsonSerializerDefaults.Web)));
 [Fact]public void RequireVersionReasonAndPositiveDelta(){var errors=ManagementEndpoints.Validate(new StockAdjustment("restock",0," ",0,""));Assert.Contains("quantity",errors.Keys);Assert.Contains("reason",errors.Keys);Assert.Contains("stockVersion",errors.Keys);Assert.Contains("idempotencyKey",errors.Keys);}
 [Fact]public void ZeroAbsoluteCorrectionIsValid()=>Assert.Empty(ManagementEndpoints.Validate(new StockAdjustment("correction",0,"Physical count",1,"new-request")));
}

using MerchantOS.Api;
using Xunit;
public sealed class ReportingTests {
 [Fact]public void RiyadhMidnightIsPreviousUtcDay(){var p=ReportingEndpoints.Period("today",null,null,false,DateTimeOffset.Parse("2026-01-01T22:00:00Z"));Assert.Equal(new DateOnly(2026,1,2),p.From);Assert.Equal(DateTime.Parse("2026-01-01T21:00:00Z").ToUniversalTime(),p.StartUtc);Assert.Equal(TimeSpan.FromDays(1),p.EndUtc-p.StartUtc);}
 [Theory][InlineData("2026-01-05","2026-01-04")][InlineData("bad","2026-01-04")][InlineData("2020-01-01","2026-01-04")][InlineData("2026-02-01","2026-02-01")]
 public void RejectInvalidRanges(string from,string to)=>Assert.Throws<ArgumentException>(()=>ReportingEndpoints.Period("custom",from,to,false,DateTimeOffset.Parse("2026-01-10T00:00:00Z")));
 [Theory][InlineData("=SUM(A1)")][InlineData(" +cmd")][InlineData("-1")][InlineData("@evil")][InlineData("\ttext")]
 public void CsvNeutralizesFormulas(string value)=>Assert.StartsWith("\"'",ReportingEndpoints.CsvCell(value));
 [Fact]public void CsvEscapesQuotesAndNewlines()=>Assert.Equal("\"a,\"\"b\"\"\nline\"",ReportingEndpoints.CsvCell("a,\"b\"\nline"));
 [Fact]public void AverageUsesExactHalalas(){Assert.Equal(0,ReportingEndpoints.Average(0,0));Assert.Equal(2,ReportingEndpoints.Average(3,2));Assert.Equal(long.MaxValue,ReportingEndpoints.Average(long.MaxValue,1));}
}

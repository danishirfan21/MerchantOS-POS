using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;
public sealed class OperationalTests {
 [Fact]public async Task LivenessIsIndependentOfDatabase(){using var app=new WebApplicationFactory<Program>().WithWebHostBuilder(b=>b.UseSetting("ConnectionStrings:MerchantDb","Host=127.0.0.1;Port=1;Database=unused;Username=unused;Timeout=1"));using var c=app.CreateClient(new(){BaseAddress=new("https://localhost")});Assert.Equal(System.Net.HttpStatusCode.OK,(await c.GetAsync("/api/health/live")).StatusCode);Assert.Equal(System.Net.HttpStatusCode.ServiceUnavailable,(await c.GetAsync("/api/health/ready")).StatusCode);}
 [Fact]public void StagingRefusesMissingProtectedConfiguration(){using var app=new WebApplicationFactory<Program>().WithWebHostBuilder(b=>b.UseEnvironment("Staging").UseSetting("ConnectionStrings:MerchantDb","Host=localhost;Database=unused;Username=unused"));Assert.ThrowsAny<Exception>(()=>app.CreateClient());}
 [Fact]public async Task CorrelationIsValidatedAndMetricsStayProtected(){using var app=new WebApplicationFactory<Program>().WithWebHostBuilder(b=>b.UseSetting("ConnectionStrings:MerchantDb","Host=localhost;Database=unused;Username=unused"));using var c=app.CreateClient(new(){BaseAddress=new("https://localhost")});c.DefaultRequestHeaders.Add("X-Correlation-ID","not-a-guid");var r=await c.GetAsync("/api/health/live");Assert.True(Guid.TryParse(r.Headers.GetValues("X-Correlation-ID").Single(),out _));Assert.Equal(System.Net.HttpStatusCode.Unauthorized,(await c.GetAsync("/api/ops/metrics")).StatusCode);}
}

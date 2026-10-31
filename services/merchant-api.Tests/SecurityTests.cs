using System.Net;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;
public sealed class SecurityTests {
 private static WebApplicationFactory<Program> App()=>new WebApplicationFactory<Program>().WithWebHostBuilder(b=>b.UseSetting("ConnectionStrings:MerchantDb","Host=localhost;Database=unused;Username=unused"));
 [Theory][InlineData("/api/products")][InlineData("/api/categories")][InlineData("/api/inventory/p01")][InlineData("/api/orders")][InlineData("/api/receipts")]
 public async Task AnonymousDataIs401(string path){using var app=App();using var client=app.CreateClient(new(){BaseAddress=new Uri("https://localhost")});Assert.Equal(HttpStatusCode.Unauthorized,(await client.GetAsync(path)).StatusCode);}
 [Fact]public async Task ForgedRolesAndCookiesCannotAuthenticate(){using var app=App();using var client=app.CreateClient(new(){BaseAddress=new Uri("https://localhost")});client.DefaultRequestHeaders.Add("Cookie","MerchantOS.Pos.Session=forged");client.DefaultRequestHeaders.Add("X-Role","Administrator");Assert.Equal(HttpStatusCode.Unauthorized,(await client.GetAsync("/api/orders")).StatusCode);}
 [Fact]public async Task LoginRequiresAntiforgery(){using var app=App();using var client=app.CreateClient(new(){BaseAddress=new Uri("https://localhost")});Assert.Equal(HttpStatusCode.BadRequest,(await client.PostAsync("/api/auth/login",new StringContent("{}",System.Text.Encoding.UTF8,"application/json"))).StatusCode);}
 [Fact]public async Task CsrfCookieIsSecureHttpOnlyStrictAndNotCached(){using var app=App();using var client=app.CreateClient(new(){BaseAddress=new Uri("https://localhost")});var r=await client.GetAsync("/api/auth/csrf");r.EnsureSuccessStatusCode();var cookie=r.Headers.GetValues("Set-Cookie").Single().ToLowerInvariant();Assert.Contains("secure",cookie);Assert.Contains("httponly",cookie);Assert.Contains("samesite=strict",cookie);Assert.Contains("no-store",r.Headers.CacheControl!.ToString());}
 [Fact]public async Task HttpIsNotGloballyEnabled(){using var app=App();using var client=app.CreateClient(new(){BaseAddress=new Uri("http://localhost")});Assert.Equal(HttpStatusCode.BadRequest,(await client.GetAsync("/api/auth/csrf")).StatusCode);}
}

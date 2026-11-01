using System.Diagnostics;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.HttpOverrides;
namespace MerchantOS.Operations;

// Same small operational boundary in both repositories; no shared runtime service/dependency.
public static class OperationalSecurity {
 public static bool Enabled(IConfiguration c)=>c.GetValue<bool>("Operations:Enabled");
 public static void Configure(WebApplicationBuilder b,string component) {
  foreach(var key in new[]{"ConnectionStrings:MerchantDb","ConnectionStrings:AdminSessions","Operations:CertificatePassword","Kestrel:Certificates:Default:Password","Account:Username","Account:Password","Account:MfaSecret","Account:Code","Bootstrap:Username","Bootstrap:Password"}){
   if(b.Configuration[key+"File"] is {} file)b.Configuration[key]=File.ReadAllText(file).TrimEnd('\r','\n');
  }
  if((b.Environment.IsStaging()||b.Environment.IsProduction())&&!Enabled(b.Configuration))throw new InvalidOperationException("Operations:Enabled is required outside Development/Testing.");
  b.Logging.ClearProviders();b.Logging.AddJsonConsole(o=>{o.IncludeScopes=true;o.TimestampFormat="yyyy-MM-ddTHH:mm:ss.fffZ";o.UseUtcTimestamp=true;});
  b.Logging.AddFilter("Microsoft.AspNetCore.Hosting.Diagnostics",LogLevel.Warning);b.Logging.AddFilter("System.Net.Http.HttpClient",LogLevel.Warning);b.Logging.AddFilter("Microsoft.EntityFrameworkCore.Database.Command",LogLevel.Warning);
  b.Services.AddHttpContextAccessor();b.Services.AddTransient<CorrelationHandler>();b.Services.AddSingleton<OperationalMetrics>();
  b.WebHost.ConfigureKestrel(o=>{o.AddServerHeader=false;o.Limits.MaxRequestBodySize=65536;o.Limits.RequestHeadersTimeout=TimeSpan.FromSeconds(20);});
  if(!Enabled(b.Configuration))return;
  string Required(string key)=>!string.IsNullOrWhiteSpace(b.Configuration[key])?b.Configuration[key]!:throw new InvalidOperationException("Missing required setting: "+key);
  if(b.Configuration.GetValue<bool>("Security:AllowLoopbackHttp"))throw new InvalidOperationException("Operational staging forbids the development HTTP exception.");
  var hosts=Required("AllowedHosts");if(hosts.Split(';').Any(h=>h.Contains('*')))throw new InvalidOperationException("Explicit AllowedHosts required.");
  _=IPAddress.Parse(Required("Operations:TrustedProxy"));
  var path=Required("Operations:KeyPath");var cert=X509CertificateLoader.LoadPkcs12FromFile(Required("Operations:CertificatePath"),Required("Operations:CertificatePassword"),X509KeyStorageFlags.EphemeralKeySet);
  if(!cert.HasPrivateKey||cert.NotAfter.ToUniversalTime()<=DateTime.UtcNow||cert.NotBefore.ToUniversalTime()>DateTime.UtcNow)throw new InvalidOperationException("Valid private key-protection certificate required.");
  Directory.CreateDirectory(path);
  if(!OperatingSystem.IsWindows()){
   var mode=File.GetUnixFileMode(path);if((mode&(UnixFileMode.GroupRead|UnixFileMode.GroupWrite|UnixFileMode.GroupExecute|UnixFileMode.OtherRead|UnixFileMode.OtherWrite|UnixFileMode.OtherExecute))!=0)throw new InvalidOperationException("Key directory must be private (0700).");
  }
  var dp=b.Services.AddDataProtection().SetApplicationName("MerchantOS."+component).SetDefaultKeyLifetime(TimeSpan.FromDays(30)).PersistKeysToFileSystem(new DirectoryInfo(path)).ProtectKeysWithCertificate(cert);
  var previous=b.Configuration["Operations:PreviousCertificatePath"];
  if(!string.IsNullOrEmpty(previous))dp.UnprotectKeysWithAnyCertificate(cert,X509CertificateLoader.LoadPkcs12FromFile(previous,Required("Operations:CertificatePassword"),X509KeyStorageFlags.EphemeralKeySet));
  b.Services.Configure<ForwardedHeadersOptions>(o=>{
   o.ForwardedHeaders=ForwardedHeaders.XForwardedFor|ForwardedHeaders.XForwardedProto;o.ForwardLimit=1;o.KnownProxies.Clear();o.KnownIPNetworks.Clear();o.KnownProxies.Add(IPAddress.Parse(Required("Operations:TrustedProxy")));
  });
 }
 public static HttpClientHandler HttpHandler(IConfiguration config) {
  var h=new HttpClientHandler{UseCookies=false,AllowAutoRedirect=false};var path=config["Operations:CaPath"];
  if(!string.IsNullOrEmpty(path)){
   var ca=X509CertificateLoader.LoadCertificateFromFile(path);
   h.ServerCertificateCustomValidationCallback=(_,cert,_,errors)=>{
    if(cert is null||(errors&(SslPolicyErrors.RemoteCertificateNameMismatch|SslPolicyErrors.RemoteCertificateNotAvailable))!=0)return false;
    using var chain=new X509Chain();chain.ChainPolicy.TrustMode=X509ChainTrustMode.CustomRootTrust;chain.ChainPolicy.CustomTrustStore.Add(ca);chain.ChainPolicy.RevocationMode=X509RevocationMode.NoCheck;return chain.Build(cert);
   };
  }
  return h;
 }
 public static void UseOperationalBoundary(this WebApplication app) {
  var enabled=Enabled(app.Configuration);
  if(enabled){
   app.Use(async(context,next)=>{
    var forwarded=context.Request.Headers.Keys.Any(k=>k.StartsWith("X-Forwarded-",StringComparison.OrdinalIgnoreCase)||k.Equals("Forwarded",StringComparison.OrdinalIgnoreCase));
    var peer=context.Connection.RemoteIpAddress?.MapToIPv4();if(forwarded&&!Equals(peer,IPAddress.Parse(app.Configuration["Operations:TrustedProxy"]!))){context.Response.StatusCode=400;return;}await next();
   });app.UseForwardedHeaders();
  }
  app.Use(async(context,next)=>{
   var incoming=context.Request.Headers["X-Correlation-ID"].ToString();var correlation=Guid.TryParse(incoming,out var id)?id.ToString("N"):Guid.NewGuid().ToString("N");context.TraceIdentifier=correlation;context.Response.Headers["X-Correlation-ID"]=correlation;
   context.Response.Headers["X-Content-Type-Options"]="nosniff";context.Response.Headers["Referrer-Policy"]="same-origin";context.Response.Headers.CacheControl="no-store";
   if(enabled){context.Response.Headers["Strict-Transport-Security"]="max-age=86400";context.Response.Headers["X-Frame-Options"]="DENY";}
   using var scope=app.Logger.BeginScope(new Dictionary<string,object>{{"CorrelationId",correlation}});var watch=Stopwatch.StartNew();
   try{await next();}
   catch(Exception ex)when(ex is not OperationCanceledException){
    app.Logger.LogError("Request failed; category {Category}; component {Component}",ex.GetType().Name,app.Environment.ApplicationName);
    var unavailable=ex is HttpRequestException or TimeoutException || ex is Npgsql.NpgsqlException and not Npgsql.PostgresException || ex is Npgsql.PostgresException pg && (pg.SqlState.StartsWith("08",StringComparison.Ordinal)||pg.SqlState is "57P01" or "57P02" or "57P03");
    if(!context.Response.HasStarted){context.Response.Clear();context.Response.StatusCode=ex is BadHttpRequestException bad?bad.StatusCode:unavailable?503:500;context.Response.Headers["X-Content-Type-Options"]="nosniff";context.Response.Headers["Referrer-Policy"]="same-origin";if(enabled){context.Response.Headers["Strict-Transport-Security"]="max-age=86400";context.Response.Headers["X-Frame-Options"]="DENY";}context.Response.Headers.CacheControl="no-store";context.Response.Headers["X-Correlation-ID"]=correlation;await context.Response.WriteAsJsonAsync(new{message="Service unavailable or operation result uncertain. Retry reads; for checkout/stock changes retain the same request key.",correlationId=correlation});}
   }
   finally{
    var route=(context.GetEndpoint() as Microsoft.AspNetCore.Routing.RouteEndpoint)?.RoutePattern.RawText??"unmatched";
    app.Services.GetRequiredService<OperationalMetrics>().Record(route,context.Response.StatusCode,watch.Elapsed.TotalMilliseconds);
    app.Logger.LogInformation("Request {Method} {Route} status {Status} durationMs {DurationMs} component {Component}",context.Request.Method,route,context.Response.StatusCode,Math.Round(watch.Elapsed.TotalMilliseconds,2),app.Environment.ApplicationName);
   }
  });
 }
 public static void InitializeKeys(WebApplication app,string[] args) {
  if(!Enabled(app.Configuration))return;
  var protector=app.Services.GetRequiredService<IDataProtectionProvider>().CreateProtector("MerchantOS.StartupProbe");
  if(protector.Unprotect(protector.Protect("ready"))!="ready")throw new InvalidOperationException("Protected key initialization failed.");
  if(args.Contains("--rotate-keys")||args.Contains("--revoke-keys")){
   if(!app.Configuration.GetValue<bool>("Operations:AllowKeyCommand"))throw new InvalidOperationException("Key commands require explicit operator authorization.");
   var manager=app.Services.GetRequiredService<Microsoft.AspNetCore.DataProtection.KeyManagement.IKeyManager>();
   if(args.Contains("--revoke-keys"))manager.RevokeAllKeys(DateTimeOffset.UtcNow,"Operator incident revocation");
   manager.CreateNewKey(DateTimeOffset.UtcNow,DateTimeOffset.UtcNow.AddDays(30));Console.WriteLine("Protected key operation completed; key material was not logged.");
  }
 }
 public static async Task<int> HealthProbe(string path) {
  try{var config=new ConfigurationBuilder().AddEnvironmentVariables().Build();using var client=new HttpClient(HttpHandler(config)){Timeout=TimeSpan.FromSeconds(3)};using var response=await client.GetAsync("https://localhost:8443"+path);return response.IsSuccessStatusCode?0:1;}catch{return 1;}
 }
}
public sealed class CorrelationHandler(IHttpContextAccessor accessor):DelegatingHandler {
 protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,CancellationToken ct){if(accessor.HttpContext is {} context)request.Headers.TryAddWithoutValidation("X-Correlation-ID",context.TraceIdentifier);return base.SendAsync(request,ct);}
}
public sealed class OperationalMetrics {
 private readonly System.Collections.Concurrent.ConcurrentDictionary<string,long> counts=new();private long durationMicros;
 private static readonly System.Diagnostics.Metrics.Meter Meter=new("MerchantOS.Operations");private static readonly System.Diagnostics.Metrics.Counter<long> Requests=Meter.CreateCounter<long>("merchantos.requests");private static readonly System.Diagnostics.Metrics.Histogram<double> Duration=Meter.CreateHistogram<double>("merchantos.request.duration","ms");
 public void Record(string route,int status,double ms){counts.AddOrUpdate(status.ToString(),1,(_,n)=>n+1);Interlocked.Add(ref durationMicros,(long)(ms*1000));Requests.Add(1,new KeyValuePair<string,object?>("route",route),new("status",status));Duration.Record(ms,new KeyValuePair<string,object?>("route",route));}
 public object Snapshot()=>new{requestsByStatus=counts,totalDurationMs=Interlocked.Read(ref durationMicros)/1000m,scope="single-process; reset on restart"};
}

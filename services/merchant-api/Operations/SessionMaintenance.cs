using Npgsql;
namespace MerchantOS.Api;
public sealed class SessionMaintenance(NpgsqlDataSource db,ILogger<SessionMaintenance> log):BackgroundService {
 protected override async Task ExecuteAsync(CancellationToken stoppingToken){using var timer=new PeriodicTimer(TimeSpan.FromMinutes(1));while(await timer.WaitForNextTickAsync(stoppingToken)){
  try{await using var cmd=db.CreateCommand("DELETE FROM auth_sessions WHERE id IN (SELECT id FROM auth_sessions WHERE expires_at<=now() ORDER BY expires_at LIMIT 1000)");var n=await cmd.ExecuteNonQueryAsync(stoppingToken);log.LogInformation("Session cleanup removed {Count} expired records",n);}catch(Exception e)when(e is not OperationCanceledException){log.LogWarning("Session cleanup unavailable; category {Category}",e.GetType().Name);}
 }}
}

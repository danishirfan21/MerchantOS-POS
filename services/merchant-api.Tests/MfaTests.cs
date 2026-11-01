using System.Text;
using MerchantOS.Api.Security;
using OtpNet;
using Xunit;
public sealed class MfaTests {
 [Theory]
 [InlineData(59L,"287082")]
 [InlineData(1111111109L,"081804")]
 [InlineData(1111111111L,"050471")]
 [InlineData(1234567890L,"005924")]
 [InlineData(2000000000L,"279037")]
 [InlineData(20000000000L,"353130")]
 public void UsesRfc6238Sha1VectorsWithSixDigitTruncation(long timestamp,string expected){var secret=Encoding.ASCII.GetBytes("12345678901234567890");var now=DateTimeOffset.FromUnixTimeSeconds(timestamp).UtcDateTime;Assert.Equal(expected,new Totp(secret).ComputeTotp(now));Assert.True(IdentitySecurity.VerifyTotp(secret,expected,now,out var step));Assert.Equal(timestamp/30,step);}
 [Fact]public void OnlyOneStepOfClockSkewIsAccepted(){var key=Encoding.ASCII.GetBytes("12345678901234567890");var now=DateTimeOffset.FromUnixTimeSeconds(1234567890).UtcDateTime;var code=new Totp(key).ComputeTotp(now);Assert.True(IdentitySecurity.VerifyTotp(key,code,now.AddSeconds(30),out _));Assert.True(IdentitySecurity.VerifyTotp(key,code,now.AddSeconds(-30),out _));Assert.False(IdentitySecurity.VerifyTotp(key,code,now.AddSeconds(60),out _));}
 [Theory][InlineData(null)][InlineData("")][InlineData("12345")][InlineData("1234567")][InlineData("abcdef")][InlineData("１２３４５６")]
 public void MalformedCodesAreRejected(string? code){Assert.False(IdentitySecurity.VerifyTotp(new byte[32],code,DateTime.UtcNow,out _));}
 [Theory][InlineData("short",false)][InlineData("              ",false)][InlineData("long enough replacement",true)]
 public void PasswordPolicy(string value,bool valid)=>Assert.Equal(valid,IdentitySecurity.PasswordValid(value));
}

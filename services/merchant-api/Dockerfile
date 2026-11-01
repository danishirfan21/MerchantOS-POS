FROM mcr.microsoft.com/dotnet/sdk:10.0@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b AS build
WORKDIR /src
COPY services/merchant-api/MerchantOS.Api.csproj ./services/merchant-api/
RUN dotnet restore services/merchant-api/MerchantOS.Api.csproj
COPY services/merchant-api/ ./services/merchant-api/
RUN dotnet publish services/merchant-api/MerchantOS.Api.csproj -c Release -o /publish --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:10.0@sha256:de0ee358cdd672f7017a003bed21e9ac9ed48a27c922a59b18175b6e82fa7fee
WORKDIR /app
COPY --from=build /publish/ ./
ENV ASPNETCORE_URLS=https://+:8443 DOTNET_EnableDiagnostics=0
USER $APP_UID
EXPOSE 8443
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s CMD ["dotnet","MerchantOS.Api.dll","--healthcheck"]
ENTRYPOINT ["dotnet","MerchantOS.Api.dll"]

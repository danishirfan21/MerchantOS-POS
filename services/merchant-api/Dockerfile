FROM mcr.microsoft.com/dotnet/sdk:10.0@sha256:fe0fd4e93bd2fbb47c883b7a6369e5c8d3db8bf01cdc5981f6ee35fbdf3ff4fb AS build
WORKDIR /src
COPY services/merchant-api/MerchantOS.Api.csproj ./services/merchant-api/
RUN dotnet restore services/merchant-api/MerchantOS.Api.csproj
COPY services/merchant-api/ ./services/merchant-api/
RUN dotnet publish services/merchant-api/MerchantOS.Api.csproj -c Release -o /publish --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:10.0@sha256:bfd912c83295ce66d4b706ebb8541b9f14259b0e76fbb88b2751f58ce2399d2e
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /publish/ ./
ENV ASPNETCORE_URLS=https://+:8443 DOTNET_EnableDiagnostics=0
USER $APP_UID
EXPOSE 8443
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s CMD ["dotnet","MerchantOS.Api.dll","--healthcheck"]
ENTRYPOINT ["dotnet","MerchantOS.Api.dll"]

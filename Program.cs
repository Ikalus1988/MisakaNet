using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.AspNetCore.Http;

namespace MisakaNet
{
    public static class LaunchTokenProvider
    {
        public static string Token { get; set; }
    }

    public class Program
    {
        public static void Main(string[] args)
        {
            // Generate a one‑time launch token and expose it to the server
            LaunchTokenProvider.Token = Guid.NewGuid().ToString();
            Console.WriteLine($"[REDACTED:credential] Launch token: {LaunchTokenProvider.Token}");

            var builder = WebApplication.CreateBuilder(args);
            var app = builder.Build();

            // Middleware that handles the “open with token” flow
            app.UseMiddleware<LaunchTokenMiddleware>();

            // Your existing endpoints go here
            app.MapGet("/", async context =>
            {
                // Example: check auth cookie
                if (!context.Request.Cookies.ContainsKey("auth"))
                {
                    context.Response.StatusCode = 401;
                    await context.Response.WriteAsync("authentication required; reopen the URL printed by the service");
                    return;
                }

                await context.Response.WriteAsync("Hello, world!");
            });

            app.Run();
        }
    }
}

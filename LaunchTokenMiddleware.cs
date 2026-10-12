using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace MisakaNet
{
    /// <summary>
    /// Middleware that accepts a one‑time launch token and issues a long‑lived auth cookie.
    /// </summary>
    public class LaunchTokenMiddleware
    {
        private readonly RequestDelegate _next;

        public LaunchTokenMiddleware(RequestDelegate next)
        {
            _next = next;
        }

        public async Task InvokeAsync(HttpContext context)
        {
            // Handle the special /open?token=… endpoint
            if (context.Request.Path.Equals("/open") &&
                context.Request.Query.ContainsKey("token"))
            {
                var token = context.Request.Query["token"];
                if (token == LaunchTokenProvider.Token)
                {
                    // Issue a persistent auth cookie (expires in 30 days)
                    context.Response.Cookies.Append(
                        "auth",
                        "true",
                        new CookieOptions
                        {
                            HttpOnly = true,
                            Secure = true,
                            Expires = DateTimeOffset.UtcNow.AddDays(30)
                        });

                    //

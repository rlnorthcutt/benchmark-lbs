use axum::{
    extract::Query,
    response::{Html, IntoResponse, Json},
    routing::get,
    Router,
};
use axum_server::tls_rustls::RustlsConfig;
use serde::{Deserialize, Serialize};
use std::{env, net::SocketAddr};
use tower_http::cors::CorsLayer;

#[tokio::main]
async fn main() {
    // Build our application with routes
    let app = Router::new()
        .route("/", get(root))
        .route("/api/health", get(health))
        .route("/api/compute/fibonacci", get(compute_fibonacci))
        .layer(CorsLayer::permissive());

    let cert_path = env::var("TLS_CERT_PATH").unwrap_or_else(|_| "/certs/server.crt".to_string());
    let key_path = env::var("TLS_KEY_PATH").unwrap_or_else(|_| "/certs/server.key".to_string());

    let tls_config = RustlsConfig::from_pem_file(&cert_path, &key_path)
        .await
        .expect("failed to load TLS configuration");

    // Run it with TLS on localhost:3000
    let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
    println!(
        "🚀 Server running on https://{} (cert: {}, key: {})",
        addr, cert_path, key_path
    );

    axum_server::bind_rustls(addr, tls_config)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

// Root endpoint - simple HTML response
async fn root() -> Html<&'static str> {
    Html(
        r#"
        <!DOCTYPE html>
        <html>
        <head>
            <title>Rust Backend - Benchmark</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #333; }
                code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
                .endpoint { margin: 15px 0; padding: 10px; background: #f9f9f9; border-left: 3px solid #007bff; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🦀 Rust Backend API</h1>
                <p>This is a high-performance Rust backend with compute-intensive endpoints for benchmarking.</p>

                <h2>Available Endpoints:</h2>
                <div class="endpoint">
                    <strong>GET /api/health</strong> - Health check
                </div>
                <div class="endpoint">
                    <strong>GET /api/compute/fibonacci?n=30</strong> - Compute Fibonacci number (default n=30)
                </div>
            </div>
        </body>
        </html>
        "#,
    )
}

// Health check endpoint
#[derive(Serialize)]
struct HealthResponse {
    status: String,
    message: String,
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        message: "Rust backend is running".to_string(),
    })
}

// Fibonacci computation (CPU-intensive)
#[derive(Deserialize)]
struct FibonacciQuery {
    #[serde(default = "default_fib_n")]
    n: u32,
}

fn default_fib_n() -> u32 {
    30
}

#[derive(Serialize)]
struct FibonacciResponse {
    n: u32,
    result: u64,
    message: String,
}

async fn compute_fibonacci(Query(params): Query<FibonacciQuery>) -> impl IntoResponse {
    let n = params.n.min(50); // Limit to prevent excessive computation

    // Spawn blocking task for CPU-intensive work
    let result = tokio::task::spawn_blocking(move || fibonacci(n))
        .await
        .unwrap();

    Json(FibonacciResponse {
        n,
        result,
        message: format!("Fibonacci number at position {}", n),
    })
}

fn fibonacci(n: u32) -> u64 {
    match n {
        0 => 0,
        1 => 1,
        _ => {
            let mut a = 0u64;
            let mut b = 1u64;
            for _ in 2..=n {
                let temp = a.wrapping_add(b);
                a = b;
                b = temp;
            }
            b
        }
    }
}

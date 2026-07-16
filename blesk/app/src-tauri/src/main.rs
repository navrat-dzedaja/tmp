#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use blesk_core::sources::m3u;

/// Fetch a text resource (playlist, repository index) on behalf of the UI —
/// the webview itself has no cross-origin network access.
#[tauri::command]
async fn fetch_text(url: String) -> Result<String, String> {
    let response = reqwest::get(&url).await.map_err(|e| e.to_string())?;
    if !response.status().is_success() {
        return Err(format!("HTTP {}", response.status()));
    }
    response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
fn parse_m3u(text: String) -> Result<m3u::Playlist, String> {
    m3u::parse(&text).map_err(|e| e.to_string())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![fetch_text, parse_m3u])
        .run(tauri::generate_context!())
        .expect("failed to run Blesk");
}

use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("invalid URL: {0}")]
    Url(#[from] url::ParseError),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("malformed playlist: {0}")]
    Playlist(String),
    #[error("portal error: {0}")]
    Portal(String),
    #[error("transport error: {0}")]
    Transport(String),
}

pub type Result<T> = std::result::Result<T, Error>;

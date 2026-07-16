use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MediaKind {
    Live,
    Movie,
    Series,
}

/// A single browsable item (channel, movie, series) regardless of source.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MediaItem {
    pub id: String,
    pub kind: MediaKind,
    pub name: String,
    #[serde(default)]
    pub poster: Option<String>,
    #[serde(default)]
    pub group: Option<String>,
    /// XMLTV / EPG channel id, when known.
    #[serde(default)]
    pub epg_id: Option<String>,
}

/// A playable stream resolved from a source or addon.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StreamRef {
    pub url: String,
    #[serde(default)]
    pub name: Option<String>,
    /// Extra HTTP headers the player must send (Referer, User-Agent, ...).
    #[serde(default)]
    pub headers: Vec<(String, String)>,
}

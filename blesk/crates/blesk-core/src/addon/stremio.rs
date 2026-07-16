//! Client for the Stremio addon protocol — gives Blesk instant access to the
//! existing addon ecosystem (catalogs, metadata, streams).
//!
//! Protocol: `{base}/manifest.json`, `{base}/catalog/{type}/{id}.json`,
//! `{base}/meta/{type}/{id}.json`, `{base}/stream/{type}/{id}.json`.

use serde::{Deserialize, Serialize};
use url::Url;

use crate::Result;

#[derive(Debug, Clone)]
pub struct Client {
    base: Url,
}

impl Client {
    /// Accepts the addon base URL or its full `.../manifest.json` URL.
    pub fn new(addon_url: &str) -> Result<Self> {
        let url = Url::parse(addon_url)?;
        let mut base = url.to_string();
        if let Some(stripped) = base.strip_suffix("manifest.json") {
            base = stripped.to_string();
        }
        if !base.ends_with('/') {
            base.push('/');
        }
        Ok(Self {
            base: Url::parse(&base)?,
        })
    }

    pub fn manifest_url(&self) -> Url {
        self.base.join("manifest.json").expect("valid path")
    }

    pub fn catalog_url(&self, media_type: &str, catalog_id: &str) -> Result<Url> {
        self.resource("catalog", media_type, catalog_id)
    }

    pub fn meta_url(&self, media_type: &str, id: &str) -> Result<Url> {
        self.resource("meta", media_type, id)
    }

    pub fn stream_url(&self, media_type: &str, id: &str) -> Result<Url> {
        self.resource("stream", media_type, id)
    }

    fn resource(&self, resource: &str, media_type: &str, id: &str) -> Result<Url> {
        Ok(self
            .base
            .join(&format!("{resource}/{media_type}/{id}.json"))?)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StremioManifest {
    pub id: String,
    pub name: String,
    /// Stremio versions are not guaranteed to be strict semver.
    pub version: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub types: Vec<String>,
    #[serde(default)]
    pub catalogs: Vec<CatalogDef>,
    /// Strings or objects depending on the addon; kept raw.
    #[serde(default)]
    pub resources: Vec<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CatalogDef {
    #[serde(rename = "type")]
    pub media_type: String,
    pub id: String,
    #[serde(default)]
    pub name: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CatalogResponse {
    #[serde(default)]
    pub metas: Vec<MetaPreview>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MetaPreview {
    pub id: String,
    #[serde(rename = "type")]
    pub media_type: String,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub poster: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StreamsResponse {
    #[serde(default)]
    pub streams: Vec<Stream>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Stream {
    #[serde(default)]
    pub url: Option<String>,
    #[serde(default, rename = "externalUrl")]
    pub external_url: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub title: Option<String>,
}

pub fn parse_manifest(body: &[u8]) -> Result<StremioManifest> {
    Ok(serde_json::from_slice(body)?)
}

pub fn parse_catalog(body: &[u8]) -> Result<CatalogResponse> {
    Ok(serde_json::from_slice(body)?)
}

pub fn parse_streams(body: &[u8]) -> Result<StreamsResponse> {
    Ok(serde_json::from_slice(body)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builds_resource_urls_from_manifest_url() {
        let client = Client::new("https://addon.example.com/manifest.json").unwrap();
        assert_eq!(
            client.manifest_url().as_str(),
            "https://addon.example.com/manifest.json"
        );
        assert_eq!(
            client.catalog_url("movie", "top").unwrap().as_str(),
            "https://addon.example.com/catalog/movie/top.json"
        );
        assert_eq!(
            client
                .stream_url("series", "tt0903747:1:3")
                .unwrap()
                .as_str(),
            "https://addon.example.com/stream/series/tt0903747:1:3.json"
        );
    }

    #[test]
    fn accepts_base_url_with_path() {
        let client = Client::new("https://host.example.com/addon").unwrap();
        assert_eq!(
            client.manifest_url().as_str(),
            "https://host.example.com/addon/manifest.json"
        );
    }

    #[test]
    fn parses_catalog_and_streams() {
        let catalog = parse_catalog(
            br#"{"metas":[{"id":"tt0903747","type":"series","name":"Breaking Bad",
                 "poster":"https://img.example/p.jpg"}]}"#,
        )
        .unwrap();
        assert_eq!(catalog.metas[0].id, "tt0903747");

        let streams = parse_streams(
            br#"{"streams":[{"url":"https://cdn.example/e.mp4","title":"1080p"},
                            {"externalUrl":"https://web.example/watch"}]}"#,
        )
        .unwrap();
        assert_eq!(
            streams.streams[0].url.as_deref(),
            Some("https://cdn.example/e.mp4")
        );
        assert_eq!(
            streams.streams[1].external_url.as_deref(),
            Some("https://web.example/watch")
        );
    }
}

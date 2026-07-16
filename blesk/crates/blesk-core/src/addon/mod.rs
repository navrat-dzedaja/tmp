//! Addon manifests and repository indexes — Kodi-style distribution:
//! a repository is a static JSON file hosted anywhere; addons are versioned
//! (semver) and update-checked against it. See docs/ADDON_SPEC.md.

pub mod stremio;

use semver::{Version, VersionReq};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Manifest {
    /// Reverse-DNS id, e.g. `org.iptv-org.playlist`.
    pub id: String,
    pub name: String,
    pub version: Version,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub author: Option<String>,
    #[serde(default)]
    pub icon: Option<String>,
    /// Requirement on the core version, e.g. `">=0.1"`.
    #[serde(default)]
    pub core: Option<VersionReq>,
    #[serde(flatten)]
    pub kind: Kind,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "kebab-case")]
pub enum Kind {
    /// Stremio-compatible HTTP addon (catalogs, metadata, streams).
    StremioAddon { url: String },
    /// M3U/M3U8 playlist with optional XMLTV EPG.
    M3uSource {
        url: String,
        #[serde(default)]
        epg_url: Option<String>,
    },
    /// Xtream Codes server; credentials are entered by the user on install.
    XtreamSource {
        #[serde(default)]
        server: Option<String>,
    },
    /// Stalker/Ministra portal; MAC and credentials entered on install.
    StalkerSource {
        #[serde(default)]
        portal: Option<String>,
    },
    /// Sandboxed JS scraper (planned).
    Script { entry: String },
}

impl Manifest {
    /// Whether this addon can run on the given core version.
    pub fn supports_core(&self, core_version: &Version) -> bool {
        self.core
            .as_ref()
            .map(|req| req.matches(core_version))
            .unwrap_or(true)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RepositoryIndex {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    pub addons: Vec<RepositoryEntry>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RepositoryEntry {
    pub id: String,
    pub name: String,
    pub version: Version,
    /// URL of a `manifest.json` or a zip package containing one.
    pub download: String,
    /// Required for zip packages; hex-encoded SHA-256 of the package.
    #[serde(default)]
    pub sha256: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
}

impl RepositoryIndex {
    pub fn parse(body: &[u8]) -> crate::Result<Self> {
        Ok(serde_json::from_slice(body)?)
    }

    /// Entries with a newer version than the installed `(id, version)` pairs.
    pub fn updates_for<'a>(&'a self, installed: &[(String, Version)]) -> Vec<&'a RepositoryEntry> {
        self.addons
            .iter()
            .filter(|entry| {
                installed
                    .iter()
                    .any(|(id, version)| *id == entry.id && entry.version > *version)
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manifest_roundtrip_with_tagged_kind() {
        let json = r#"{
            "id": "org.iptv-org.playlist",
            "name": "iptv-org",
            "version": "1.0.0",
            "type": "m3u-source",
            "url": "https://iptv-org.github.io/iptv/index.m3u",
            "epg_url": null,
            "core": ">=0.1"
        }"#;
        let manifest: Manifest = serde_json::from_str(json).unwrap();
        assert_eq!(manifest.id, "org.iptv-org.playlist");
        assert!(matches!(&manifest.kind, Kind::M3uSource { url, .. }
            if url == "https://iptv-org.github.io/iptv/index.m3u"));
        assert!(manifest.supports_core(&Version::new(0, 1, 0)));
        assert!(!manifest.supports_core(&Version::new(0, 0, 9)));

        let reencoded = serde_json::to_string(&manifest).unwrap();
        let reparsed: Manifest = serde_json::from_str(&reencoded).unwrap();
        assert_eq!(manifest, reparsed);
    }

    #[test]
    fn stremio_addon_manifest() {
        let json = r#"{
            "id": "com.example.catalog",
            "name": "Katalog",
            "version": "1.2.0",
            "type": "stremio-addon",
            "url": "https://addon.example.com/manifest.json"
        }"#;
        let manifest: Manifest = serde_json::from_str(json).unwrap();
        assert!(matches!(manifest.kind, Kind::StremioAddon { .. }));
    }

    #[test]
    fn repository_update_check() {
        let index = RepositoryIndex::parse(
            br#"{
                "id": "cz.example.repo",
                "name": "Repo",
                "addons": [
                    {"id": "a", "name": "A", "version": "1.1.0", "download": "https://x/a.json"},
                    {"id": "b", "name": "B", "version": "2.0.0", "download": "https://x/b.zip",
                     "sha256": "deadbeef"}
                ]
            }"#,
        )
        .unwrap();

        let installed = vec![
            ("a".to_string(), Version::new(1, 1, 0)),
            ("b".to_string(), Version::new(1, 9, 3)),
        ];
        let updates = index.updates_for(&installed);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].id, "b");
    }
}

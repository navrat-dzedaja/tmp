//! Single-pass M3U / M3U8 (extended M3U) playlist parser.
//!
//! Handles `#EXTINF` attributes (`tvg-id`, `tvg-name`, `tvg-logo`,
//! `group-title`, ...), quoted values with commas, and `#EXTGRP`.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::{Error, Result};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Playlist {
    pub items: Vec<Item>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Item {
    pub name: String,
    pub url: String,
    /// Seconds; `-1.0` for live streams.
    pub duration: f64,
    /// `group-title` attribute or preceding `#EXTGRP`.
    pub group: Option<String>,
    /// All `#EXTINF` attributes, keys lowercased.
    pub attrs: BTreeMap<String, String>,
}

impl Item {
    pub fn attr(&self, name: &str) -> Option<&str> {
        self.attrs.get(name).map(String::as_str)
    }
}

pub fn parse(text: &str) -> Result<Playlist> {
    let mut items = Vec::new();
    let mut pending: Option<(f64, BTreeMap<String, String>, String)> = None;
    let mut extgrp: Option<String> = None;

    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        if let Some(rest) = line.strip_prefix("#EXTINF:") {
            pending = Some(parse_extinf(rest));
        } else if let Some(rest) = line.strip_prefix("#EXTGRP:") {
            let group = rest.trim();
            extgrp = (!group.is_empty()).then(|| group.to_string());
        } else if line.starts_with('#') {
            continue;
        } else {
            // Without a preceding #EXTINF only URL-looking lines count as
            // entries; this rejects HTML error pages served instead of a playlist.
            if pending.is_none() && !line.contains("://") {
                continue;
            }
            let (duration, attrs, name) =
                pending
                    .take()
                    .unwrap_or((-1.0, BTreeMap::new(), String::new()));
            let name = if name.is_empty() {
                line.to_string()
            } else {
                name
            };
            let group = attrs.get("group-title").cloned().or_else(|| extgrp.clone());
            items.push(Item {
                name,
                url: line.to_string(),
                duration,
                group,
                attrs,
            });
        }
    }

    if items.is_empty() && !text.contains("#EXTM3U") {
        return Err(Error::Playlist("not an M3U playlist".into()));
    }
    Ok(Playlist { items })
}

/// Parses the part after `#EXTINF:` into (duration, attributes, display name).
fn parse_extinf(rest: &str) -> (f64, BTreeMap<String, String>, String) {
    let chars: Vec<char> = rest.chars().collect();
    let len = chars.len();
    let mut pos = 0;

    while pos < len && chars[pos] != ',' && !chars[pos].is_whitespace() {
        pos += 1;
    }
    let duration: f64 = chars[..pos]
        .iter()
        .collect::<String>()
        .parse()
        .unwrap_or(-1.0);

    let mut attrs = BTreeMap::new();
    loop {
        while pos < len && chars[pos].is_whitespace() {
            pos += 1;
        }
        if pos >= len {
            return (duration, attrs, String::new());
        }
        if chars[pos] == ',' {
            let name: String = chars[pos + 1..].iter().collect();
            return (duration, attrs, name.trim().to_string());
        }

        let key_start = pos;
        while pos < len && chars[pos] != '=' && chars[pos] != ',' && !chars[pos].is_whitespace() {
            pos += 1;
        }
        let key: String = chars[key_start..pos].iter().collect();
        if pos >= len || chars[pos] != '=' {
            if key.is_empty() {
                pos += 1; // stray character, keep moving
            }
            continue;
        }
        pos += 1; // skip '='

        let value: String = if pos < len && chars[pos] == '"' {
            pos += 1;
            let start = pos;
            while pos < len && chars[pos] != '"' {
                pos += 1;
            }
            let value = chars[start..pos].iter().collect();
            if pos < len {
                pos += 1; // closing quote
            }
            value
        } else {
            let start = pos;
            while pos < len && chars[pos] != ',' && !chars[pos].is_whitespace() {
                pos += 1;
            }
            chars[start..pos].iter().collect()
        };
        if !key.is_empty() {
            attrs.insert(key.to_ascii_lowercase(), value);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = r#"#EXTM3U
#EXTINF:-1 tvg-id="ct1.cz" tvg-logo="https://logo.example/ct1.png" group-title="Zprávy, CZ",ČT1 HD
http://example.com/ct1.m3u8
#EXTGRP:Sport
#EXTINF:-1,ČT Sport
http://example.com/sport.ts
#EXTINF:120 tvg-name=Film,Nějaký film, druhá část
http://example.com/movie.mp4
"#;

    #[test]
    fn parses_extended_playlist() {
        let playlist = parse(SAMPLE).unwrap();
        assert_eq!(playlist.items.len(), 3);

        let ct1 = &playlist.items[0];
        assert_eq!(ct1.name, "ČT1 HD");
        assert_eq!(ct1.url, "http://example.com/ct1.m3u8");
        assert_eq!(ct1.duration, -1.0);
        assert_eq!(ct1.attr("tvg-id"), Some("ct1.cz"));
        // quoted value with a comma survives
        assert_eq!(ct1.group.as_deref(), Some("Zprávy, CZ"));

        let sport = &playlist.items[1];
        assert_eq!(sport.name, "ČT Sport");
        assert_eq!(sport.group.as_deref(), Some("Sport"), "EXTGRP applies");

        let movie = &playlist.items[2];
        assert_eq!(movie.duration, 120.0);
        assert_eq!(movie.attr("tvg-name"), Some("Film"));
        // name is everything after the first top-level comma
        assert_eq!(movie.name, "Nějaký film, druhá část");
    }

    #[test]
    fn bare_urls_use_url_as_name() {
        let playlist = parse("#EXTM3U\nhttp://example.com/stream.ts\n").unwrap();
        assert_eq!(playlist.items[0].name, "http://example.com/stream.ts");
    }

    #[test]
    fn rejects_non_playlist() {
        assert!(parse("<html>not a playlist</html>").is_err());
    }

    #[test]
    fn empty_playlist_with_header_is_ok() {
        assert!(parse("#EXTM3U\n").unwrap().items.is_empty());
    }
}

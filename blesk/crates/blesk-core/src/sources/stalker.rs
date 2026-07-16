//! Stalker / Ministra portal client (sans-IO: request builders + parsers).
//!
//! Flow: `handshake` → token → `get_profile` → `get_genres` /
//! `get_all_channels` → `create_link` to resolve the real stream URL.

use serde::{Deserialize, Serialize};
use url::Url;

use crate::http::Request;
use crate::util::{de_opt_string, de_string};
use crate::{Error, Result};

const USER_AGENT: &str = "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 \
    (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3";

#[derive(Debug, Clone)]
pub struct Portal {
    endpoint: Url,
    mac: String,
}

impl Portal {
    /// `portal` may be a bare host (`http://tv.example.com`) or a full
    /// endpoint (`.../server/load.php`, `.../portal.php`).
    pub fn new(portal: &str, mac: &str) -> Result<Self> {
        let mut url = Url::parse(portal)?;
        if url.cannot_be_a_base() {
            return Err(Error::Portal(format!("not a portal URL: {portal}")));
        }
        if !url.path().ends_with(".php") {
            if !url.path().ends_with('/') {
                let path = format!("{}/", url.path());
                url.set_path(&path);
            }
            url = url.join("server/load.php")?;
        }
        Ok(Self {
            endpoint: url,
            mac: mac.trim().to_uppercase(),
        })
    }

    pub fn mac(&self) -> &str {
        &self.mac
    }

    fn headers(&self, token: Option<&str>) -> Vec<(String, String)> {
        let mut headers = vec![
            ("User-Agent".to_string(), USER_AGENT.to_string()),
            (
                "Cookie".to_string(),
                format!("mac={}; stb_lang=en; timezone=Europe/Prague", self.mac),
            ),
            (
                "X-User-Agent".to_string(),
                "Model: MAG250; Link: WiFi".to_string(),
            ),
        ];
        if let Some(token) = token {
            headers.push(("Authorization".to_string(), format!("Bearer {token}")));
        }
        headers
    }

    fn action(
        &self,
        kind: &str,
        action: &str,
        extra: &[(&str, &str)],
        token: Option<&str>,
    ) -> Request {
        let mut url = self.endpoint.clone();
        {
            let mut query = url.query_pairs_mut();
            query.append_pair("type", kind);
            query.append_pair("action", action);
            for (key, value) in extra {
                query.append_pair(key, value);
            }
            query.append_pair("JsHttpRequest", "1-xml");
        }
        let mut request = Request::get(url);
        request.headers = self.headers(token);
        request
    }

    pub fn handshake(&self) -> Request {
        self.action("stb", "handshake", &[("token", "")], None)
    }

    pub fn get_profile(&self, token: &str) -> Request {
        self.action("stb", "get_profile", &[], Some(token))
    }

    pub fn get_genres(&self, token: &str) -> Request {
        self.action("itv", "get_genres", &[], Some(token))
    }

    pub fn get_all_channels(&self, token: &str) -> Request {
        self.action("itv", "get_all_channels", &[], Some(token))
    }

    /// Resolves a channel `cmd` into a playable URL (returned by the portal).
    pub fn create_link(&self, token: &str, cmd: &str) -> Request {
        self.action(
            "itv",
            "create_link",
            &[
                ("cmd", cmd),
                ("series", ""),
                ("forced_storage", "undefined"),
                ("disable_ad", "0"),
                ("download", "0"),
            ],
            Some(token),
        )
    }
}

#[derive(Deserialize)]
struct Js<T> {
    js: T,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Channel {
    #[serde(deserialize_with = "de_string")]
    pub id: String,
    pub name: String,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub number: Option<String>,
    #[serde(default)]
    pub logo: Option<String>,
    /// Portal command, resolved to a real URL via `create_link`.
    pub cmd: String,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub tv_genre_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Genre {
    #[serde(deserialize_with = "de_string")]
    pub id: String,
    pub title: String,
}

pub fn parse_handshake(body: &[u8]) -> Result<String> {
    #[derive(Deserialize)]
    struct Handshake {
        token: String,
    }
    let response: Js<Handshake> = serde_json::from_slice(body)?;
    Ok(response.js.token)
}

pub fn parse_genres(body: &[u8]) -> Result<Vec<Genre>> {
    let response: Js<Vec<Genre>> = serde_json::from_slice(body)?;
    Ok(response.js)
}

pub fn parse_channels(body: &[u8]) -> Result<Vec<Channel>> {
    #[derive(Deserialize)]
    struct Data {
        data: Vec<Channel>,
    }
    let response: Js<Data> = serde_json::from_slice(body)?;
    Ok(response.js.data)
}

/// Extracts the playable URL from a `create_link` response. Portals prefix the
/// URL with a player hint like `ffmpeg http://...` or `auto http://...`.
pub fn parse_create_link(body: &[u8]) -> Result<String> {
    #[derive(Deserialize)]
    struct Link {
        cmd: String,
    }
    let response: Js<Link> = serde_json::from_slice(body)?;
    let cmd = response.js.cmd;
    let url = cmd
        .split_whitespace()
        .find(|token| {
            token.starts_with("http://")
                || token.starts_with("https://")
                || token.starts_with("rtsp://")
        })
        .unwrap_or(cmd.trim())
        .to_string();
    if url.is_empty() {
        return Err(Error::Portal("create_link returned empty cmd".into()));
    }
    Ok(url)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_portal_url_and_mac() {
        let portal = Portal::new("http://tv.example.com", "00:1a:79:aa:bb:cc").unwrap();
        assert_eq!(portal.mac(), "00:1A:79:AA:BB:CC");
        let request = portal.handshake();
        assert_eq!(
            request.url.as_str(),
            "http://tv.example.com/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        );
        let cookie = request
            .headers
            .iter()
            .find(|(name, _)| name == "Cookie")
            .map(|(_, value)| value.as_str())
            .unwrap();
        assert!(cookie.starts_with("mac=00:1A:79:AA:BB:CC;"));
    }

    #[test]
    fn keeps_explicit_php_endpoint() {
        let portal = Portal::new(
            "http://host/stalker_portal/server/load.php",
            "00:1A:79:00:00:01",
        )
        .unwrap();
        assert!(portal.get_all_channels("tok").url.as_str().starts_with(
            "http://host/stalker_portal/server/load.php?type=itv&action=get_all_channels"
        ));
    }

    #[test]
    fn authorized_requests_carry_bearer_token() {
        let portal = Portal::new("http://host", "00:1A:79:00:00:01").unwrap();
        let request = portal.create_link("tok123", "ffmpeg http://localhost/ch/1");
        assert!(request
            .headers
            .iter()
            .any(|(name, value)| name == "Authorization" && value == "Bearer tok123"));
    }

    #[test]
    fn parses_handshake_and_channels() {
        let token = parse_handshake(br#"{"js":{"token":"abc123"}}"#).unwrap();
        assert_eq!(token, "abc123");

        let channels = parse_channels(
            r#"{"js":{"data":[
                {"id": 5, "name": "ČT1", "number": "1", "logo": "http://x/1.png",
                 "cmd": "ffmpeg http://localhost/ch/5", "tv_genre_id": 2}
            ]}}"#
                .as_bytes(),
        )
        .unwrap();
        assert_eq!(channels[0].id, "5");
        assert_eq!(channels[0].tv_genre_id.as_deref(), Some("2"));
    }

    #[test]
    fn extracts_url_from_create_link_cmd() {
        let url =
            parse_create_link(br#"{"js":{"cmd":"ffmpeg http://cdn.example.com/live/5.m3u8?t=x"}}"#)
                .unwrap();
        assert_eq!(url, "http://cdn.example.com/live/5.m3u8?t=x");

        let bare = parse_create_link(br#"{"js":{"cmd":"http://cdn.example.com/5.ts"}}"#).unwrap();
        assert_eq!(bare, "http://cdn.example.com/5.ts");
    }
}

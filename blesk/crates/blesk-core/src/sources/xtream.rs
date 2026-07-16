//! Xtream Codes panel API client (sans-IO: URL builders + response parsers).

use serde::{Deserialize, Serialize};
use url::Url;

use crate::util::{de_opt_string, de_string, de_u64};
use crate::{Error, Result};

#[derive(Debug, Clone)]
pub struct Account {
    base_url: Url,
    username: String,
    password: String,
}

impl Account {
    pub fn new(server: &str, username: &str, password: &str) -> Result<Self> {
        let mut base_url = Url::parse(server)?;
        if base_url.cannot_be_a_base() {
            return Err(Error::Portal(format!("not a server URL: {server}")));
        }
        if !base_url.path().ends_with('/') {
            let path = format!("{}/", base_url.path());
            base_url.set_path(&path);
        }
        Ok(Self {
            base_url,
            username: username.to_string(),
            password: password.to_string(),
        })
    }

    fn join(&self, path: &str) -> Url {
        self.base_url.join(path).expect("valid relative path")
    }

    fn api(&self, action: Option<&str>, extra: &[(&str, &str)]) -> Url {
        let mut url = self.join("player_api.php");
        {
            let mut query = url.query_pairs_mut();
            query.append_pair("username", &self.username);
            query.append_pair("password", &self.password);
            if let Some(action) = action {
                query.append_pair("action", action);
            }
            for (key, value) in extra {
                query.append_pair(key, value);
            }
        }
        url
    }

    /// Account/server info; also serves as the login check.
    pub fn account_info_url(&self) -> Url {
        self.api(None, &[])
    }

    pub fn live_categories_url(&self) -> Url {
        self.api(Some("get_live_categories"), &[])
    }

    pub fn vod_categories_url(&self) -> Url {
        self.api(Some("get_vod_categories"), &[])
    }

    pub fn series_categories_url(&self) -> Url {
        self.api(Some("get_series_categories"), &[])
    }

    pub fn live_streams_url(&self, category_id: Option<&str>) -> Url {
        match category_id {
            Some(id) => self.api(Some("get_live_streams"), &[("category_id", id)]),
            None => self.api(Some("get_live_streams"), &[]),
        }
    }

    pub fn vod_streams_url(&self, category_id: Option<&str>) -> Url {
        match category_id {
            Some(id) => self.api(Some("get_vod_streams"), &[("category_id", id)]),
            None => self.api(Some("get_vod_streams"), &[]),
        }
    }

    pub fn series_url(&self, category_id: Option<&str>) -> Url {
        match category_id {
            Some(id) => self.api(Some("get_series"), &[("category_id", id)]),
            None => self.api(Some("get_series"), &[]),
        }
    }

    pub fn series_info_url(&self, series_id: u64) -> Url {
        self.api(
            Some("get_series_info"),
            &[("series_id", &series_id.to_string())],
        )
    }

    pub fn vod_info_url(&self, vod_id: u64) -> Url {
        self.api(Some("get_vod_info"), &[("vod_id", &vod_id.to_string())])
    }

    pub fn short_epg_url(&self, stream_id: u64) -> Url {
        self.api(
            Some("get_short_epg"),
            &[("stream_id", &stream_id.to_string())],
        )
    }

    /// Full XMLTV guide.
    pub fn xmltv_url(&self) -> Url {
        let mut url = self.join("xmltv.php");
        url.query_pairs_mut()
            .append_pair("username", &self.username)
            .append_pair("password", &self.password);
        url
    }

    /// Direct live stream URL, `extension` is typically `ts` or `m3u8`.
    pub fn live_stream_url(&self, stream_id: u64, extension: &str) -> Url {
        self.join(&format!(
            "live/{}/{}/{stream_id}.{extension}",
            self.username, self.password
        ))
    }

    pub fn movie_stream_url(&self, stream_id: u64, extension: &str) -> Url {
        self.join(&format!(
            "movie/{}/{}/{stream_id}.{extension}",
            self.username, self.password
        ))
    }

    pub fn series_episode_url(&self, episode_id: u64, extension: &str) -> Url {
        self.join(&format!(
            "series/{}/{}/{episode_id}.{extension}",
            self.username, self.password
        ))
    }
}

// Panels freely mix numbers and strings, hence the lenient deserializers.

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Category {
    #[serde(deserialize_with = "de_string")]
    pub category_id: String,
    pub category_name: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LiveStream {
    #[serde(deserialize_with = "de_u64")]
    pub stream_id: u64,
    pub name: String,
    #[serde(default)]
    pub stream_icon: Option<String>,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub epg_channel_id: Option<String>,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub category_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VodStream {
    #[serde(deserialize_with = "de_u64")]
    pub stream_id: u64,
    pub name: String,
    #[serde(default)]
    pub stream_icon: Option<String>,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub container_extension: Option<String>,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub category_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SeriesItem {
    #[serde(deserialize_with = "de_u64")]
    pub series_id: u64,
    pub name: String,
    #[serde(default)]
    pub cover: Option<String>,
    #[serde(default, deserialize_with = "de_opt_string")]
    pub category_id: Option<String>,
}

pub fn parse_categories(body: &[u8]) -> Result<Vec<Category>> {
    Ok(serde_json::from_slice(body)?)
}

pub fn parse_live_streams(body: &[u8]) -> Result<Vec<LiveStream>> {
    Ok(serde_json::from_slice(body)?)
}

pub fn parse_vod_streams(body: &[u8]) -> Result<Vec<VodStream>> {
    Ok(serde_json::from_slice(body)?)
}

pub fn parse_series(body: &[u8]) -> Result<Vec<SeriesItem>> {
    Ok(serde_json::from_slice(body)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn account() -> Account {
        Account::new("http://portal.example.com:8080", "user", "pass").unwrap()
    }

    #[test]
    fn builds_api_urls() {
        let account = account();
        assert_eq!(
            account.live_categories_url().as_str(),
            "http://portal.example.com:8080/player_api.php?username=user&password=pass&action=get_live_categories"
        );
        assert_eq!(
            account.live_streams_url(Some("7")).as_str(),
            "http://portal.example.com:8080/player_api.php?username=user&password=pass&action=get_live_streams&category_id=7"
        );
        assert_eq!(
            account.live_stream_url(42, "m3u8").as_str(),
            "http://portal.example.com:8080/live/user/pass/42.m3u8"
        );
        assert_eq!(
            account.xmltv_url().as_str(),
            "http://portal.example.com:8080/xmltv.php?username=user&password=pass"
        );
    }

    #[test]
    fn keeps_base_path_prefix() {
        let account = Account::new("http://host/panel", "u", "p").unwrap();
        assert_eq!(
            account.account_info_url().as_str(),
            "http://host/panel/player_api.php?username=u&password=p"
        );
    }

    #[test]
    fn parses_mixed_type_json() {
        // category_id as number, stream_id as string, epg id null — all common
        let body = r#"[
            {"stream_id": "15", "name": "ČT1", "stream_icon": "http://x/l.png",
             "epg_channel_id": null, "category_id": 3},
            {"stream_id": 16, "name": "Nova", "epg_channel_id": "nova.cz"}
        ]"#
        .as_bytes();
        let streams = parse_live_streams(body).unwrap();
        assert_eq!(streams[0].stream_id, 15);
        assert_eq!(streams[0].category_id.as_deref(), Some("3"));
        assert_eq!(streams[0].epg_channel_id, None);
        assert_eq!(streams[1].stream_id, 16);
        assert_eq!(streams[1].epg_channel_id.as_deref(), Some("nova.cz"));

        let categories =
            parse_categories(br#"[{"category_id": 3, "category_name": "CZ"}]"#).unwrap();
        assert_eq!(categories[0].category_id, "3");
    }
}

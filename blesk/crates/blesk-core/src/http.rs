//! Sans-IO HTTP layer: the core describes requests, the shell executes them.

use std::borrow::Cow;
use std::future::Future;

use url::Url;

use crate::Result;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Method {
    Get,
    Post,
}

#[derive(Debug, Clone)]
pub struct Request {
    pub method: Method,
    pub url: Url,
    pub headers: Vec<(String, String)>,
    pub body: Option<Vec<u8>>,
}

impl Request {
    pub fn get(url: Url) -> Self {
        Self {
            method: Method::Get,
            url,
            headers: Vec::new(),
            body: None,
        }
    }

    pub fn header(mut self, name: &str, value: &str) -> Self {
        self.headers.push((name.to_string(), value.to_string()));
        self
    }
}

#[derive(Debug, Clone)]
pub struct Response {
    pub status: u16,
    pub body: Vec<u8>,
}

impl Response {
    pub fn text(&self) -> Cow<'_, str> {
        String::from_utf8_lossy(&self.body)
    }
}

/// Implemented by the host shell (Tauri, Android, iOS, CLI). The core never
/// opens sockets itself.
pub trait Transport {
    fn send(&self, request: Request) -> impl Future<Output = Result<Response>> + Send;
}

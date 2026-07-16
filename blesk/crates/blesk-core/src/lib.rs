//! Blesk core — UI-agnostic, sans-IO player core.
//!
//! The core builds HTTP requests and parses responses; the actual transfer is
//! done by the host shell through [`http::Transport`]. This keeps the crate
//! free of system dependencies, instantly testable and embeddable on every
//! platform (desktop, mobile, TV) via thin shells.

pub mod addon;
pub mod error;
pub mod http;
pub mod model;
pub mod sources;

mod util;

pub use error::{Error, Result};

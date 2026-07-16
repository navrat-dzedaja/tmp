//! Lenient deserializers for the wild west of IPTV panel APIs, which freely
//! mix numbers, strings and null for the same field.

use serde::{Deserialize, Deserializer};

#[derive(Deserialize)]
#[serde(untagged)]
enum Flexible {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
}

impl Flexible {
    fn into_string(self) -> String {
        match self {
            Flexible::Int(n) => n.to_string(),
            Flexible::Float(f) => f.to_string(),
            Flexible::Str(s) => s,
            Flexible::Bool(b) => b.to_string(),
        }
    }
}

pub(crate) fn de_string<'de, D: Deserializer<'de>>(d: D) -> Result<String, D::Error> {
    Ok(Flexible::deserialize(d)?.into_string())
}

pub(crate) fn de_opt_string<'de, D: Deserializer<'de>>(d: D) -> Result<Option<String>, D::Error> {
    let v: Option<Flexible> = Option::deserialize(d)?;
    Ok(v.map(Flexible::into_string).filter(|s| !s.is_empty()))
}

pub(crate) fn de_u64<'de, D: Deserializer<'de>>(d: D) -> Result<u64, D::Error> {
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum V {
        Num(u64),
        Str(String),
    }
    match V::deserialize(d)? {
        V::Num(n) => Ok(n),
        V::Str(s) => s.trim().parse().map_err(serde::de::Error::custom),
    }
}

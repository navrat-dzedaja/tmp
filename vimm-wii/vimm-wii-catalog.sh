#!/bin/bash
#
# vimm-wii-catalog.sh -- build a CSV catalogue of every Wii game in Vimm's Vault
#                        and report the total download size.
#
# Written for stock macOS: bash 3.2, BSD sed/awk, system curl and perl.
# No Homebrew dependencies.
#
# What it does
#   1. Walks every section of the Wii list (# and A-Z), following pagination.
#   2. Fetches each game's detail page (cached on disk, so re-runs are cheap
#      and an interrupted run resumes where it stopped).
#   3. Parses name / region / version / year / publisher / players / serial /
#      CRC / rating / release name / download size.
#   4. Collapses titles that exist for several regions down to one row,
#      preferring Europe (order is configurable, see --region-priority).
#   5. Writes the CSV and prints the summed size at the end.
#
# Usage
#   ./vimm-wii-catalog.sh                      # full run -> wii_games.csv
#   ./vimm-wii-catalog.sh -s G --limit 5 -v    # quick smoke test
#   ./vimm-wii-catalog.sh --self-test          # offline test of the pipeline
#   ./vimm-wii-catalog.sh --keep-duplicates    # one row per region, no dedup
#
# Be nice to the server: the default is one request per second, sequentially.
# Everything is cached under .vimm-cache/, so delete that directory (or use
# --refresh) if you want fresh data.

set -u

VERSION="1.0"
BASE="https://vimm.net"
# absolute path to this script, so `xargs -P` worker mode always finds it
case "$0" in
  /*) SELF="$0" ;;
  *)  SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")" ;;
esac
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

OUT="wii_games.csv"
CACHE=".vimm-cache"
DELAY="1.0"
JOBS=1
SECTIONS=""
LIMIT=0
VERBOSE=0
KEEP_DUPES=0
REFRESH=0
EXCLUDE_EXTRAS=0
PREFER_FORMAT="wbfs"
MAX_RETRIES=4
MAX_PAGES=50
TOTAL_ROW=0
SELF_TEST=0

# Region preference, best first. Matched case-insensitively against the
# region string; a game listed for several regions gets its best match.
REGION_PRIORITY="Europe,World,United Kingdom,UK,Great Britain,England,Germany,France,Spain,Italy,Netherlands,Holland,Scandinavia,Sweden,Denmark,Norway,Finland,Portugal,Greece,Poland,Russia,Austria,Switzerland,Belgium,Ireland,Czech,Hungary,Turkey,Australia,New Zealand,USA,United States,Canada,Brazil,Mexico,Latin America,Japan,Korea,Asia,China,Taiwan,Hong Kong"

REGION_WORDS="USA|United States|Europe|Japan|World|Germany|France|Spain|Italy|Netherlands|Holland|Scandinavia|Sweden|Denmark|Norway|Finland|Portugal|Greece|Poland|Russia|Austria|Switzerland|Belgium|Ireland|Czech|Hungary|Turkey|Australia|New Zealand|Canada|Brazil|Mexico|Latin America|Korea|Asia|China|Taiwan|Hong Kong|United Kingdom|Great Britain|England|UK|Unknown"

usage() {
  sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'
  cat <<EOF

Options
  -o, --output FILE          output CSV (default: $OUT)
  -c, --cache DIR            cache directory (default: $CACHE)
  -d, --delay SECONDS        delay between HTTP requests (default: $DELAY)
  -j, --jobs N               parallel detail fetches (default: $JOBS, be gentle)
  -s, --sections "A B ..."   only these sections (use 'number' for #)
      --limit N              stop after N games (smoke testing)
      --keep-duplicates      do not collapse regional duplicates
      --region-priority LIST comma separated region preference, best first
      --format FMT           download format whose size to report (default: $PREFER_FORMAT)
      --exclude-extras       skip demos, prototypes, unlicensed, bonus, translations
      --refresh              ignore cached pages and re-download
      --total-row            append a TOTAL row to the CSV as well
      --self-test            run the offline pipeline test and exit
  -v, --verbose              chattier progress
  -h, --help                 this text
EOF
}

log()  { [ "$VERBOSE" -eq 1 ] && printf '%s\n' "$*" >&2; return 0; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# Per-process scratch files, so parallel workers never share a cookie jar.
# set_scratch is called once $CACHE is known (parent and worker alike).
set_scratch() {
  COOKIES="$CACHE/cookies.$$.txt"
  CURLERR="$CACHE/curl.$$.err"
  trap 'rm -f "$COOKIES" "$CURLERR"' EXIT INT TERM
}
COOKIES="/dev/null"
CURLERR="/dev/null"

# http_get URL OUTFILE -- retries with exponential backoff, honours $DELAY.
http_get() {
  _url="$1"; _out="$2"
  # the filter URLs are enormous; keep log lines readable
  _disp=$(printf '%s' "$_url" | cut -c1-70)
  [ "${#_url}" -gt 70 ] && _disp="$_disp..."
  _try=1
  while [ "$_try" -le "$MAX_RETRIES" ]; do
    _code=$(curl -sSL --compressed \
                 -A "$UA" \
                 -H 'Accept: text/html,application/xhtml+xml' \
                 -H 'Accept-Language: en-US,en;q=0.9' \
                 -b "$COOKIES" -c "$COOKIES" \
                 --max-time 60 \
                 -o "$_out.part" -w '%{http_code}' "$_url" 2>"$CURLERR")
    case "$_code" in
      200)
        mv "$_out.part" "$_out"
        case "$DELAY" in 0|0.0|"") : ;; *) sleep "$DELAY" ;; esac
        return 0
        ;;
      404|410)
        rm -f "$_out.part"
        warn "$_code for $_disp (skipping)"
        return 1
        ;;
      403|407)
        rm -f "$_out.part"
        warn "$_code for $_disp -- blocked (proxy policy, or Vimm rejected the request)"
        return 1
        ;;
      429|503)
        _wait=$((10 * _try))
        warn "$_code for $_disp -- rate limited, waiting ${_wait}s"
        sleep "$_wait"
        ;;
      *)
        _wait=$((2 ** _try))
        warn "HTTP $_code for $_disp (attempt $_try/$MAX_RETRIES), retrying in ${_wait}s"
        sleep "$_wait"
        ;;
    esac
    _try=$((_try + 1))
  done
  rm -f "$_out.part"
  warn "giving up on $_disp"
  [ -s "$CURLERR" ] && warn "curl said: $(tr -d '\r' <"$CURLERR" | tail -1)"
  return 1
}

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

filters_query() {
  # The "all countries / all extras / newest version" filter set, taken from
  # the Vault's own filter form.
  _c=""
  for _n in 1 2 3 35 31 4 5 6 38 43 7 8 9 10 11 12 13 27 33 34 14 15 16 30 \
            17 18 40 19 42 28 29 20 32 37 21 22 36 23 39 41 24 25 26; do
    _c="$_c&countries%5B%5D=$_n"
  done
  _extras="&translated=1&prototype=1&demo=1&unlicensed=1&bonus=1"
  [ "$EXCLUDE_EXTRAS" -eq 1 ] && _extras=""
  printf '%s' "p=list&action=filters&system=Wii&countries_all=1${_c}${_extras}&version=new&discs="
}

section_url() {
  printf '%s/vault/?%s&section=%s' "$BASE" "$(filters_query)" "$1"
}

# ---------------------------------------------------------------------------
# Parsers (perl: present on every macOS, and far safer than sed for HTML)
# ---------------------------------------------------------------------------

PARSE_LIST_PL='
use strict; use warnings;
sub dec {
  my $s = shift; return "" unless defined $s;
  $s =~ s/<[^>]*>/ /g;
  $s =~ s/&nbsp;/ /g; $s =~ s/&amp;/&/g; $s =~ s/&lt;/</g; $s =~ s/&gt;/>/g;
  $s =~ s/&quot;/"/g; $s =~ s/&#0?39;|&apos;|&rsquo;/\x27/g;
  $s =~ s/&#(\d+);/chr($1)/ge;
  $s =~ s/[\t\r\n]+/ /g; $s =~ s/\s+/ /g; $s =~ s/^ | $//g;
  return $s;
}
local $/; my $h = <STDIN>; $h = "" unless defined $h;
$h =~ s/\r?\n/ /g;
my %seen;
for my $row (split /<tr\b/i, $h) {
  next unless $row =~ m{href="(?:https?://[^/"]+)?/vault/(\d+)"}i;
  my $id = $1;
  next if $seen{$id}++;
  my ($name) = $row =~ m{href="(?:https?://[^/"]+)?/vault/\d+"[^>]*>(.*?)</a>}is;
  $name = dec($name);
  if ($name eq "") {
    ($name) = $row =~ m{href="(?:https?://[^/"]+)?/vault/\d+"[^>]*\btitle="([^"]*)"}is;
    $name = dec($name);
  }
  my @regions;
  while ($row =~ m{<img\b([^>]*)>}gis) {
    my $attrs = $1;
    my $r = "";
    if    ($attrs =~ m{\btitle="([^"]+)"}i) { $r = $1 }
    elsif ($attrs =~ m{\balt="([^"]+)"}i)   { $r = $1 }
    elsif ($attrs =~ m{\bsrc="[^"]*/([A-Za-z][A-Za-z0-9_+-]*)\.(?:png|gif|jpg|svg)"}i) { $r = $1 }
    $r = dec($r);
    $r =~ s/_/ /g;
    push @regions, $r if $r ne "" && $r !~ /^\d+$/;
  }
  my @nums = ($row =~ m{<td\b[^>]*>\s*(?:<[^>]*>\s*)*([0-9]+(?:\.[0-9]+)*)\s*(?:<[^>]*>\s*)*</td>}gis);
  my $version = @nums ? $nums[-1] : "";
  print join("\t", $id, $name, join("+", @regions), $version), "\n";
}
'

PARSE_PAGES_PL='
use strict; use warnings;
local $/; my $h = <STDIN>; $h = "" unless defined $h;
my %p;
while ($h =~ m{[?&;](?:amp;)?page=(\d+)}gi) { $p{$1} = 1 if $1 > 1 && $1 <= 500 }
print "$_\n" for sort { $a <=> $b } keys %p;
'

PARSE_DETAIL_PL='
use strict; use warnings;
my $id       = $ENV{VW_ID}       || "";
my $words    = $ENV{VW_REGIONS}  || "USA|Europe|Japan";
my $prefer   = $ENV{VW_FORMAT}   || "wbfs";
my $priolist = $ENV{VW_PRIORITY} || "Europe,USA,Japan";

sub dec {
  my $s = shift; return "" unless defined $s;
  $s =~ s/<[^>]*>/ /g;
  $s =~ s/&nbsp;/ /g; $s =~ s/&amp;/&/g; $s =~ s/&lt;/</g; $s =~ s/&gt;/>/g;
  $s =~ s/&quot;/"/g; $s =~ s/&#0?39;|&apos;|&rsquo;/\x27/g;
  $s =~ s/&#(\d+);/chr($1)/ge;
  $s =~ s/[\t\r\n]+/ /g; $s =~ s/\s+/ /g; $s =~ s/^ | $//g;
  return $s;
}

local $/; my $h = <STDIN>; $h = "" unless defined $h;
$h =~ s/\r?\n/ /g;

# --- label/value table -----------------------------------------------------
my (%f, $region_html);
for my $tr (split /<tr\b/i, $h) {
  my @cells = ($tr =~ m{<t[dh]\b[^>]*>(.*?)</t[dh]>}gis);
  next unless @cells >= 2;
  my $lab = dec($cells[0]);
  $lab =~ s/\s*#\s*$//; $lab =~ s/[:\s]+$//;
  next unless $lab =~ /^[A-Za-z][A-Za-z .\/]{1,24}$/;
  my $raw = join(" ", @cells[1 .. $#cells]);
  my $val = dec($raw);
  my $key = lc $lab;
  if (!exists $f{$key} || $f{$key} eq "") { $f{$key} = $val }
  if ($key eq "region" && !defined $region_html) { $region_html = $raw }
}

# --- title -----------------------------------------------------------------
my $name = "";
for my $re (qr{<h1\b[^>]*>(.*?)</h1>}is, qr{<h2\b[^>]*>(.*?)</h2>}is) {
  if ($h =~ $re) { my $c = dec($1); if ($c ne "" && lc($c) ne "wii") { $name = $c; last } }
}
if ($name eq "" && $h =~ m{<meta[^>]+property="og:title"[^>]+content="([^"]+)"}i) { $name = dec($1) }
if ($name eq "" && $h =~ m{<title>(.*?)</title>}is) {
  $name = dec($1);
  $name =~ s/\s*[-|]\s*(Wii|The Vault|Vimm.s Lair).*$//i;
}

# --- release (romset) name, e.g. "Foo (USA) (En,Fr)" -----------------------
my $release = "";
if ($h =~ m{<i>(.*?)</i>}is) { my $c = dec($1); $release = $c if $c =~ /\(/ }
if ($release eq "") {
  while ($h =~ m{>([^<>]{6,240})<}g) {
    my $c = dec($1);
    if ($c =~ /\((?:$words)\b/i) { $release = $c; last }
  }
}

# --- region ---------------------------------------------------------------
my @regions;
if (defined $region_html) {
  while ($region_html =~ m{<img\b([^>]*)>}gis) {
    my $a = $1; my $r = "";
    if    ($a =~ m{\btitle="([^"]+)"}i) { $r = $1 }
    elsif ($a =~ m{\balt="([^"]+)"}i)   { $r = $1 }
    elsif ($a =~ m{\bsrc="[^"]*/([A-Za-z][A-Za-z0-9_+-]*)\.(?:png|gif|jpg|svg)"}i) { $r = $1 }
    $r = dec($r); $r =~ s/_/ /g;
    push @regions, $r if $r ne "" && $r !~ /^\d+$/;
  }
  my $txt = dec($region_html);
  push @regions, $txt if !@regions && $txt =~ /^(?:$words)/i;
}
if (!@regions && $release =~ /\(((?:$words)(?:\s*,\s*(?:$words))*)\)/i) {
  push @regions, split(/\s*,\s*/, $1);
}
if (!@regions && ($f{region} || "") ne "") { push @regions, $f{region} }
my %rs; my @ru = grep { !$rs{lc $_}++ } @regions;
my $region = join("+", @ru);
$region = "Unknown" if $region eq "";

# --- rating ---------------------------------------------------------------
my ($rating, $votes) = ("", "");
if (($f{overall} || "") =~ /([\d.]+)\s*(?:\(\s*(\d+)\s*votes?\s*\))?/) { $rating = $1; $votes = defined $2 ? $2 : "" }

# --- size -----------------------------------------------------------------
# The Vault prints the size next to the Download button, for whatever format
# the Format selector currently shows (.wbfs is the Wii default). Several
# fallbacks, because that box has changed shape over the years.
my $SZ = qr{([\d]+(?:\.\d+)?)\s*(?:&nbsp;|\s)*\b(TB|GB|MB|KB)\b};
my ($size, $unit, $src) = ("", "", "none");

if ($h =~ m{\.\Q$prefer\E\b.{0,800}?$SZ}is)          { ($size,$unit,$src) = ($1,$2,"format-label") }
if ($size eq "" && $h =~ m{Download.{0,600}?$SZ}is)   { ($size,$unit,$src) = ($1,$2,"after-download") }
if ($size eq "") {
  my @m;
  while ($h =~ m{$SZ(?=.{0,600}?Download)}gis) { push @m, [$1,$2] }
  if (@m) { ($size,$unit) = @{$m[-1]}; $src = "before-download" }
}
if ($size eq "") {
  my @m;
  while ($h =~ m{$SZ}gis) { push @m, [$1,$2] }
  if (@m) { ($size,$unit) = @{$m[-1]}; $src = "last-on-page" }
}

my $gb = 0;
if ($size ne "") {
  my $u = uc $unit;
  $gb = $u eq "TB" ? $size * 1024
      : $u eq "GB" ? $size
      : $u eq "MB" ? $size / 1024
      :              $size / (1024 * 1024);
}
$gb = sprintf("%.4f", $gb);

# --- which download format the size belongs to ----------------------------
my $format = "";
if (($f{format} || "") =~ /\.?([A-Za-z0-9]+)/) { $format = lc $1 }
$format = $prefer if $format eq "" || $format eq "format";

# --- dedup keys -----------------------------------------------------------
my $norm = lc $name;
$norm =~ s/&/and/g; $norm =~ s/[^a-z0-9]+/ /g; $norm =~ s/^ | $//g;

my $prio = 999; my $i = 0;
for my $p (split /\s*,\s*/, $priolist) {
  $i++;
  next if $p eq "";
  for my $r (@ru) { if (lc($r) eq lc($p)) { $prio = $i if $i < $prio } }
}

my $version = $f{version} || "";
my $vkey = 0;
if ($version =~ /^(\d+)(?:\.(\d+))?/) { $vkey = $1 * 1000 + (defined $2 ? $2 : 0) }

sub cell { my $s = shift; $s = "" unless defined $s; $s =~ s/[\t\r\n]+/ /g; $s =~ s/\s+/ /g; $s =~ s/^ | $//g; return $s }

print join("\t", map { cell($_) }
  $norm, $prio, $vkey, $gb, $id,
  $name, $region, $version,
  ($f{year} || ""), ($f{publisher} || ""), ($f{players} || ""),
  ($f{serial} || ""), ($f{crc} || ""), $rating, $votes,
  $release, $format, ($f{verified} || ""), $src), "\n";
'

TO_CSV_PL='
use strict; use warnings;
sub csvq { my $s = shift; $s = "" unless defined $s; $s =~ s/"/""/g; return "\"$s\"" }
print join(",", map { csvq($_) } qw(
  name region version year publisher players serial crc rating votes
  release_name format size_gb verified vault_id url duplicates_dropped)), "\n";
while (my $l = <STDIN>) {
  chomp $l;
  my @c = split /\t/, $l, -1;
  next unless @c >= 19;
  my ($gb,$id,$name,$region,$ver,$year,$pub,$players,$serial,$crc,$rating,$votes,$rel,$fmt,$verified) =
     ($c[3],$c[4],$c[5],$c[6],$c[7],$c[8],$c[9],$c[10],$c[11],$c[12],$c[13],$c[14],$c[15],$c[16],$c[17]);
  my $dropped = defined $c[19] ? $c[19] : "";
  $gb = sprintf("%.2f", $gb || 0);
  print join(",", map { csvq($_) }
    $name, $region, $ver, $year, $pub, $players, $serial, $crc, $rating, $votes,
    $rel, $fmt, $gb, $verified, $id, "https://vimm.net/vault/$id", $dropped), "\n";
}
'

# ---------------------------------------------------------------------------
# Worker mode: fetch a single detail page into the cache (used with xargs -P)
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--fetch-one" ]; then
  CACHE="${VW_CACHE:?--fetch-one is an internal mode}"
  DELAY="${VW_DELAY:-1}"; VERBOSE="${VW_VERBOSE:-0}"
  MAX_RETRIES="${VW_RETRIES:-4}"
  _id="${2:?--fetch-one needs a vault id}"
  set_scratch
  _dst="$CACHE/detail/$_id.html"
  if [ -s "$_dst" ] && [ "${VW_REFRESH:-0}" -eq 0 ]; then exit 0; fi
  http_get "$BASE/vault/$_id" "$_dst" || exit 0
  exit 0
fi

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    -o|--output)          OUT="$2"; shift 2 ;;
    -c|--cache)           CACHE="$2"; shift 2 ;;
    -d|--delay)           DELAY="$2"; shift 2 ;;
    -j|--jobs)            JOBS="$2"; shift 2 ;;
    -s|--sections)        SECTIONS="$2"; shift 2 ;;
    --limit)              LIMIT="$2"; shift 2 ;;
    --keep-duplicates)    KEEP_DUPES=1; shift ;;
    --region-priority)    REGION_PRIORITY="$2"; shift 2 ;;
    --format)             PREFER_FORMAT="$(printf '%s' "$2" | tr 'A-Z' 'a-z' | sed 's/^\.//')"; shift 2 ;;
    --exclude-extras)     EXCLUDE_EXTRAS=1; shift ;;
    --refresh)            REFRESH=1; shift ;;
    --total-row)          TOTAL_ROW=1; shift ;;
    --self-test)          SELF_TEST=1; shift ;;
    -v|--verbose)         VERBOSE=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

[ "$SECTIONS" = "" ] && SECTIONS="number A B C D E F G H I J K L M N O P Q R S T U V W X Y Z"

command -v curl >/dev/null 2>&1 || die "curl not found"
command -v perl >/dev/null 2>&1 || die "perl not found"

WORK="$CACHE/work"
mkdir -p "$CACHE/detail" "$CACHE/list" "$WORK" || die "cannot create $CACHE"
set_scratch

export VW_REGIONS="$REGION_WORDS"
export VW_FORMAT="$PREFER_FORMAT"
export VW_PRIORITY="$REGION_PRIORITY"

# ---------------------------------------------------------------------------
# Pipeline stages that need no network (also exercised by --self-test)
# ---------------------------------------------------------------------------

# parse every cached detail page listed in $WORK/ids.txt -> $WORK/rows.tsv
parse_details() {
  : >"$WORK/rows.tsv"
  _n=0; _bad=0
  while read -r _id; do
    [ -n "$_id" ] || continue
    _f="$CACHE/detail/$_id.html"
    [ -s "$_f" ] || { _bad=$((_bad + 1)); continue; }
    VW_ID="$_id" perl -e "$PARSE_DETAIL_PL" <"$_f" >>"$WORK/rows.tsv" || _bad=$((_bad + 1))
    _n=$((_n + 1))
  done <"$WORK/ids.txt"
  log "parsed $_n detail pages ($_bad missing/failed)"
}

# dedup: winner per normalised name, plus a list of what was dropped
dedup_rows() {
  LC_ALL=C sort -t "$(printf '\t')" -k1,1 -k2,2n -k3,3nr -k4,4nr -k5,5n \
    "$WORK/rows.tsv" >"$WORK/rows.sorted.tsv"

  if [ "$KEEP_DUPES" -eq 1 ]; then
    awk -F'\t' -v OFS='\t' '{print $0, ""}' "$WORK/rows.sorted.tsv" >"$WORK/final.tsv"
    return
  fi

  awk -F'\t' -v OFS='\t' '
    function emit() { if (have) print win, drop }
    {
      if ($1 != cur) { emit(); cur = $1; win = $0; drop = ""; have = 1 }
      else {
        d = $6 " (" $7 ")"
        if ($8 != "") d = d " v" $8
        d = d " #" $5
        drop = (drop == "" ? d : drop " | " d)
      }
    }
    END { emit() }
  ' "$WORK/rows.sorted.tsv" >"$WORK/final.tsv"
}

write_csv() {
  perl -e "$TO_CSV_PL" <"$WORK/final.tsv" >"$OUT" || die "CSV generation failed"
}

print_summary() {
  # Sum the same 2-decimal values the CSV carries, so adding up the size_gb
  # column in a spreadsheet gives exactly this total.
  awk -F'\t' -v out="$OUT" '
    { n++; s += sprintf("%.2f", $4) + 0; if ($4 + 0 == 0) unknown++ }
    END {
      tb = s / 1024
      printf "\n"
      printf "Games in CSV (after region dedup): %d\n", n
      if (unknown > 0) printf "Games with no size found:           %d (counted as 0)\n", unknown
      printf "CSV written to:                     %s\n", out
      printf "\n"
      printf "TOTAL DOWNLOAD SIZE: %.2f GB  (%.2f TB)\n", s, tb
      printf "Disk to buy (+10%% headroom): %.2f TB\n", tb * 1.1
    }
  ' "$WORK/final.tsv"

  if [ "$TOTAL_ROW" -eq 1 ]; then
    awk -F'\t' '
      { s += sprintf("%.2f", $4) + 0 }
      END { printf "\"TOTAL\",\"\",\"\",\"\",\"\",\"\",\"\",\"\",\"\",\"\",\"\",\"\",\"%.2f\",\"\",\"\",\"\",\"\"\n", s }
    ' "$WORK/final.tsv" >>"$OUT"
  fi
}

# ---------------------------------------------------------------------------
# Self test: run the whole parse -> dedup -> CSV -> sum pipeline on fixtures
# ---------------------------------------------------------------------------
if [ "$SELF_TEST" -eq 1 ]; then
  CACHE="$(mktemp -d "${TMPDIR:-/tmp}/vimm-selftest.XXXXXX")"
  WORK="$CACHE/work"; OUT="$CACHE/out.csv"
  mkdir -p "$CACHE/detail" "$WORK"
  echo "self-test workspace: $CACHE"

  make_detail() { # id name region version size
    cat >"$CACHE/detail/$1.html" <<EOF
<html><head><title>$2 - Wii - The Vault</title></head><body>
<h2>$2</h2>
<table class="rounded">
<tr><td class="gray"><b>Region</b></td><td><img src="/images/flags/$3.png" title="$3"></td></tr>
<tr><td class="gray"><b>Players</b></td><td>2</td></tr>
<tr><td class="gray"><b>Year</b></td><td>2009</td></tr>
<tr><td class="gray"><b>Publisher</b></td><td>Atari SA</td></tr>
<tr><td class="gray"><b>Serial #</b></td><td>RVL-RGQE-USA</td></tr>
<tr><td class="gray"><b>Overall</b></td><td>8.9 (21 votes)</td></tr>
<tr><td colspan="2"><i>$2 ($3) (En,Fr,De)</i></td></tr>
<tr><td class="gray"><b>CRC</b></td><td>a6539a7a</td></tr>
<tr><td class="gray"><b>Verified</b></td><td>2026-08-04</td></tr>
<tr><td class="gray"><b>Format</b></td><td><select><option>.wbfs</option><option>.iso</option></select></td></tr>
<tr><td class="gray"><b>Version</b></td><td>$4</td></tr>
<tr><td colspan="2"><input type="submit" value="Download">&nbsp;$5</td></tr>
</table></body></html>
EOF
  }

  make_detail 101 "Ghostbusters: The Video Game" Europe 1.0 "2.75 GB"
  make_detail 102 "Ghostbusters: The Video Game" USA   1.1 "2.81 GB"
  make_detail 103 "Ghost Squad"                  Japan 1.0 "512 MB"
  make_detail 104 "Ghost Squad"                  Europe 1.0 "600 MB"
  make_detail 105 "Geon Cube"                    USA   1.0 "1.00 GB"
  printf '101\n102\n103\n104\n105\n' >"$WORK/ids.txt"

  # list-page parser fixture
  cat >"$CACHE/list.html" <<'EOF'
<table><tr><th>Title</th><th>Region</th><th>Version</th></tr>
<tr><td><a href="/vault/101" title="x">Ghostbusters: The Video Game</a></td>
    <td><img src="/images/flags/Europe.png" title="Europe"></td><td>1.0</td></tr>
<tr><td><a href="/vault/103">Ghost Squad</a></td>
    <td><img src="/images/flags/Japan.png" title="Japan"></td><td>1.0</td></tr>
<tr><td><a href="/vault/106">Girls Life: Sleepover Party</a></td>
    <td><img src="/images/flags/Australia.png" title="Australia"><img src="/images/flags/Europe.png" title="Europe"></td><td>1.0</td></tr>
</table>
EOF

  fail=0
  chk() { if [ "$2" = "$3" ]; then echo "  ok   $1"; else echo "  FAIL $1: got [$2] want [$3]"; fail=1; fi }

  # CSV-aware field extractor -- cut -d, would trip over quoted commas
  csvfield() { # csvfield FILE LINE FIELDNO
    sed -n "$2p" "$1" | perl -e '
      my $n = shift; my $l = <STDIN>; $l = "" unless defined $l; chomp $l;
      my @f; while ($l =~ /\G"((?:[^"]|"")*)"(?:,|$)/gc) { my $v = $1; $v =~ s/""/"/g; push @f, $v }
      print defined $f[$n-1] ? $f[$n-1] : "";' "$3"
  }

  ln="$(perl -e "$PARSE_LIST_PL" <"$CACHE/list.html")"
  chk "list rows"        "$(printf '%s\n' "$ln" | wc -l | tr -d ' ')" "3"
  chk "list id+name"     "$(printf '%s\n' "$ln" | head -1 | cut -f1,2)" "$(printf '101\tGhostbusters: The Video Game')"
  chk "list multiflag"   "$(printf '%s\n' "$ln" | sed -n 3p | cut -f3)" "Australia+Europe"
  chk "list version"     "$(printf '%s\n' "$ln" | head -1 | cut -f4)" "1.0"

  parse_details
  chk "rows parsed"      "$(wc -l <"$WORK/rows.tsv" | tr -d ' ')" "5"
  chk "detail name"      "$(head -1 "$WORK/rows.tsv" | cut -f6)" "Ghostbusters: The Video Game"
  chk "detail region"    "$(head -1 "$WORK/rows.tsv" | cut -f7)" "Europe"
  chk "detail publisher" "$(head -1 "$WORK/rows.tsv" | cut -f10)" "Atari SA"
  chk "detail serial"    "$(head -1 "$WORK/rows.tsv" | cut -f12)" "RVL-RGQE-USA"
  chk "detail rating"    "$(head -1 "$WORK/rows.tsv" | cut -f14)" "8.9"
  chk "detail votes"     "$(head -1 "$WORK/rows.tsv" | cut -f15)" "21"
  chk "detail release"   "$(head -1 "$WORK/rows.tsv" | cut -f16)" "Ghostbusters: The Video Game (Europe) (En,Fr,De)"
  chk "detail format"    "$(head -1 "$WORK/rows.tsv" | cut -f17)" "wbfs"
  chk "size GB"          "$(head -1 "$WORK/rows.tsv" | cut -f4)" "2.7500"
  chk "size MB->GB"      "$(awk -F'\t' '$5==103{print $4}' "$WORK/rows.tsv")" "0.5000"

  dedup_rows
  chk "deduped count"    "$(wc -l <"$WORK/final.tsv" | tr -d ' ')" "3"
  chk "EU beats US"      "$(awk -F'\t' '$1 ~ /^ghostbusters/{print $7}' "$WORK/final.tsv")" "Europe"
  chk "EU beats JP"      "$(awk -F'\t' '$1 == "ghost squad"{print $7}' "$WORK/final.tsv")" "Europe"
  chk "dropped recorded" "$(awk -F'\t' '$1 ~ /^ghostbusters/{print $20}' "$WORK/final.tsv")" \
                         "Ghostbusters: The Video Game (USA) v1.1 #102"

  write_csv
  chk "csv header"       "$(head -1 "$OUT" | cut -d, -f1-3)" '"name","region","version"'
  chk "csv data rows"    "$(( $(wc -l <"$OUT" | tr -d ' ') - 1 ))" "3"
  chk "csv quoting"      "$(grep -c '^"Geon Cube","USA","1.0"' "$OUT" | tr -d ' ')" "1"
  chk "csv release col"  "$(csvfield "$OUT" 4 11)" "Ghostbusters: The Video Game (Europe) (En,Fr,De)"
  chk "csv size col"     "$(csvfield "$OUT" 4 13)" "2.75"
  chk "csv verified col" "$(csvfield "$OUT" 4 14)" "2026-08-04"
  chk "csv url col"      "$(csvfield "$OUT" 4 16)" "https://vimm.net/vault/101"
  chk "csv dropped col"  "$(csvfield "$OUT" 4 17)" "Ghostbusters: The Video Game (USA) v1.1 #102"
  # 2.75 + 0.5859375 (600MB) + 1.00
  chk "total sum"        "$(awk -F'\t' '{s+=$4} END{printf "%.2f", s}' "$WORK/final.tsv")" "4.34"

  KEEP_DUPES=1; dedup_rows
  chk "keep-duplicates"  "$(wc -l <"$WORK/final.tsv" | tr -d ' ')" "5"

  echo
  if [ "$fail" -eq 0 ]; then echo "self-test: all checks passed"; else echo "self-test: FAILURES"; fi
  rm -rf "$CACHE"
  exit "$fail"
fi

# ---------------------------------------------------------------------------
# Stage 1: section lists -> ids
# ---------------------------------------------------------------------------
printf 'Vimm Wii catalogue v%s -- sections: %s\n' "$VERSION" "$SECTIONS" >&2
: >"$WORK/index.tsv"

for sec in $SECTIONS; do
  pages="1"
  first="$CACHE/list/$sec-1.html"
  if [ ! -s "$first" ] || [ "$REFRESH" -eq 1 ]; then
    http_get "$(section_url "$sec")" "$first" || { warn "section $sec unavailable"; continue; }
  fi
  extra=$(perl -e "$PARSE_PAGES_PL" <"$first" | head -"$MAX_PAGES")
  for p in $extra; do
    f="$CACHE/list/$sec-$p.html"
    if [ ! -s "$f" ] || [ "$REFRESH" -eq 1 ]; then
      http_get "$(section_url "$sec")&page=$p" "$f" || continue
    fi
    pages="$pages $p"
  done
  for p in $pages; do
    f="$CACHE/list/$sec-$p.html"
    [ -s "$f" ] || continue
    perl -e "$PARSE_LIST_PL" <"$f" >>"$WORK/index.tsv"
  done
  n=$(wc -l <"$WORK/index.tsv" | tr -d ' ')
  printf 'section %-6s done (%s entries so far)\n' "$sec" "$n" >&2
done

LC_ALL=C sort -u -t "$(printf '\t')" -k1,1 "$WORK/index.tsv" -o "$WORK/index.tsv"
cut -f1 "$WORK/index.tsv" | LC_ALL=C sort -u -n >"$WORK/ids.all"
if [ "$LIMIT" -gt 0 ]; then head -"$LIMIT" "$WORK/ids.all" >"$WORK/ids.txt"; else cp "$WORK/ids.all" "$WORK/ids.txt"; fi

total=$(wc -l <"$WORK/ids.txt" | tr -d ' ')
if [ "$total" -eq 0 ]; then
  if [ -z "$(ls -A "$CACHE/list" 2>/dev/null)" ]; then
    die "no list page could be downloaded at all -- vimm.net was unreachable from
       this machine (network down, DNS, a VPN/proxy, or Vimm blocking the request).
       Check with: curl -sI https://vimm.net/vault/Wii | head -1"
  fi
  die "list pages downloaded but no games parsed -- the markup has probably changed.
       Inspect $CACHE/list/*.html and adjust PARSE_LIST_PL."
fi
printf '%s games to fetch\n' "$total" >&2

# ---------------------------------------------------------------------------
# Stage 2: detail pages (cached, resumable)
# ---------------------------------------------------------------------------
export VW_CACHE="$CACHE" VW_DELAY="$DELAY" VW_VERBOSE="$VERBOSE" \
       VW_RETRIES="$MAX_RETRIES" VW_REFRESH="$REFRESH"

need=0
: >"$WORK/todo.txt"
while read -r id; do
  if [ ! -s "$CACHE/detail/$id.html" ] || [ "$REFRESH" -eq 1 ]; then
    printf '%s\n' "$id" >>"$WORK/todo.txt"; need=$((need + 1))
  fi
done <"$WORK/ids.txt"
printf '%s already cached, %s to download\n' "$((total - need))" "$need" >&2

if [ "$need" -gt 0 ]; then
  if [ "$JOBS" -gt 1 ]; then
    xargs -n1 -P "$JOBS" "$SELF" --fetch-one <"$WORK/todo.txt"
  else
    i=0
    while read -r id; do
      i=$((i + 1))
      printf '\r  fetching %s/%s (id %s)   ' "$i" "$need" "$id" >&2
      "$SELF" --fetch-one "$id"
    done <"$WORK/todo.txt"
    printf '\n' >&2
  fi
fi

# ---------------------------------------------------------------------------
# Stage 3-5: parse, dedup, CSV, total
# ---------------------------------------------------------------------------
parse_details
[ -s "$WORK/rows.tsv" ] || die "nothing parsed -- inspect $CACHE/detail/*.html"
# audit trail: size_gb, id, name, which regex found the size
cut -f4,5,6,19 "$WORK/rows.tsv" >"$WORK/size-source.tsv"

dedup_rows
write_csv
print_summary

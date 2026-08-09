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
#   2. Picks the preferred regional variant of each title from the listing, then
#      fetches only those detail pages (cached on disk, so re-runs are cheap and
#      an interrupted run resumes where it stopped).
#   3. Parses name / region / version / year / publisher / players / serial /
#      CRC / rating / romset name / exact download size.
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
USE_FILTERS=1
PRINT_URL=""
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
      --filters              use the country-filter URL form (default: it lists
                             every regional variant)
      --plain                use the plain /vault/Wii/X listing instead. Beware:
                             it returns far fewer entries per section
      --print-url SECTION    print the list URL for SECTION and exit (debugging)
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
  # Two ways to ask for a section listing:
  #   plain    https://vimm.net/vault/Wii/G          (what the site links to)
  #   filters  https://vimm.net/vault/?p=list&action=filters&...&section=G
  # The plain listing already includes every regional variant, so it is the
  # default; --filters switches to the explicit filter form.
  if [ "$USE_FILTERS" -eq 1 ]; then
    printf '%s/vault/?%s&section=%s' "$BASE" "$(filters_query)" "$1"
  elif [ "$1" = "number" ]; then
    printf '%s/vault/?p=list&system=Wii&section=number' "$BASE"
  else
    printf '%s/vault/Wii/%s' "$BASE" "$1"
  fi
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
  $s =~ s/&#x([0-9a-fA-F]+);/chr(hex($1))/ge;
  $s =~ s/&#(\d+);/chr($1)/ge;
  $s =~ s/[\t\r\n]+/ /g; $s =~ s/\s+/ /g; $s =~ s/^ | $//g;
  return $s;
}
local $/; my $h = <STDIN>; $h = "" unless defined $h;
$h =~ s/\r?\n/ /g;
my %seen;
for my $row (split /<tr\b/i, $h) {
  # Every real row carries a hidden decoy link first:
  #   <a href="/vault/999999" style="display:none">9</a><a href= "/vault/17478">..
  # Note the space after href= on the real one. So: consider every anchor,
  # throw away the hidden ones, and take the first that survives.
  # Cells are: 0 = title, 1 = region flags, 2 = version, then extras.
  # Extract them BEFORE any other //g match on this row: a //g loop leaves
  # pos() set, and the next //g would start from there and shift every column.
  my @cells = ($row =~ m{<td\b[^>]*>(.*?)</td>}gis);
  next unless @cells;

  my ($id, $name) = ("", "");
  my $titlecell = $cells[0];
  while ($titlecell =~ m{<a\b([^>]*)>(.*?)</a>}gis) {
    my ($attrs, $text) = ($1, $2);
    next if $attrs =~ /display\s*:\s*none/i;
    next unless $attrs =~ m{\bhref\s*=\s*["\x27]?\s*(?:https?://[^/"\x27]+)?/vault/(\d+)}i;
    next if $1 eq "999999";
    ($id, $name) = ($1, dec($text));
    last;
  }
  next unless $id ne "" && $name ne "";
  next if $seen{$id}++;

  my @regions;
  if (defined $cells[1]) {
    while ($cells[1] =~ m{<img\b([^>]*)>}gis) {
      my $attrs = $1;
      my $r = "";
      if    ($attrs =~ m{\btitle=["\x27]([^"\x27]+)}i) { $r = $1 }
      elsif ($attrs =~ m{\balt=["\x27]([^"\x27]+)}i)   { $r = $1 }
      elsif ($attrs =~ m{\bsrc=["\x27][^"\x27]*/([A-Za-z][A-Za-z0-9_+-]*)\.(?:png|gif|jpg|svg)}i) { $r = $1 }
      $r = dec($r); $r =~ s/_/ /g;
      push @regions, $r if $r ne "" && $r !~ /^\d+$/;
    }
  }

  my $version = "";
  if (defined $cells[2]) {
    my $v = dec($cells[2]);
    $version = $v if $v =~ /^\d+(?:\.\d+)*$/;
  }
  if ($version eq "") {   # fall back to any version-shaped cell
    for my $c (@cells) {
      my $v = dec($c);
      if ($v =~ /^\d+\.\d+$/) { $version = $v; last }
    }
  }
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

# Rank the list entries so the regional winner can be picked BEFORE any detail
# page is fetched. The listing already carries name, region and version, which
# is everything the dedup needs -- so only the winners get downloaded instead of
# every regional variant of every title.
PARSE_INDEX_PL='
use strict; use warnings;
my $priolist = $ENV{VW_PRIORITY} || "Europe,USA,Japan";
while (my $l = <STDIN>) {
  chomp $l;
  my ($id, $name, $regions, $version) = split /\t/, $l, -1;
  next unless defined $name && $name ne "";
  $regions = "" unless defined $regions;
  $version = "" unless defined $version;

  my @ru = split /\+/, $regions;
  @ru = ("Unknown") unless @ru;

  my $prio = 999; my $i = 0;
  for my $p (split /\s*,\s*/, $priolist) {
    $i++;
    next if $p eq "";
    for my $r (@ru) { if (lc($r) eq lc($p)) { $prio = $i if $i < $prio } }
  }

  my $vkey = 0;
  $vkey = $1 * 1000 + (defined $2 ? $2 : 0) if $version =~ /^(\d+)(?:\.(\d+))?/;

  my $norm = lc $name;
  $norm =~ s/&/and/g; $norm =~ s/[^a-z0-9]+/ /g; $norm =~ s/^ | $//g;

  print join("\t", $norm, $prio, $vkey, $id, $name, $regions, $version), "\n";
}
'

PARSE_DETAIL_PL='
use strict; use warnings;
use MIME::Base64 ();
my $id       = $ENV{VW_ID}       || "";
my $words    = $ENV{VW_REGIONS}  || "USA|Europe|Japan";
my $prefer   = $ENV{VW_FORMAT}   || "wbfs";
my $priolist = $ENV{VW_PRIORITY} || "Europe,USA,Japan";

sub dec {
  my $s = shift; return "" unless defined $s;
  $s =~ s/<[^>]*>/ /g;
  $s =~ s/&nbsp;/ /g; $s =~ s/&amp;/&/g; $s =~ s/&lt;/</g; $s =~ s/&gt;/>/g;
  $s =~ s/&quot;/"/g; $s =~ s/&#0?39;|&apos;|&rsquo;/\x27/g;
  $s =~ s/&#x([0-9a-fA-F]+);/chr(hex($1))/ge;
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
  # A <select> (Version, Format, Disc #) must contribute only its chosen
  # option, otherwise the value comes out as "1.0 1.1 1.0".
  if ($raw =~ m{<select\b}i) {
    if    ($raw =~ m{<option\b[^>]*\bselected\b[^>]*>([^<]*)}i) { $raw = $1 }
    elsif ($raw =~ m{<option\b[^>]*>([^<]*)}i)                  { $raw = $1 }
  }
  my $val = dec($raw);
  my $key = lc $lab;
  if (!exists $f{$key} || $f{$key} eq "") { $f{$key} = $val }
  if ($key eq "region" && !defined $region_html) { $region_html = $raw }
}

# --- title -----------------------------------------------------------------
# og:title carries exactly the game name. The page has no <h1>/<h2> for the
# title -- the only headings belong to the console nav menu, which is how an
# earlier version of this script ended up calling every game "Nintendo".
my $name = "";
if ($h =~ m{<meta[^>]+property=["\x27]og:title["\x27][^>]+content=["\x27]([^"\x27]+)}i) {
  $name = dec($1);
}
if ($name eq "" && $h =~ m{<title>(.*?)</title>}is) {
  # "The Vault: Ghostbusters: The Video Game (Wii)"
  $name = dec($1);
  $name =~ s/^\s*The Vault\s*:\s*//i;
  $name =~ s/\s*\((?:Wii|NES|SNES|N64|GameCube|GBA|DS|PS1|PS2|PSP)\)\s*$//i;
}

# --- the JS media payload --------------------------------------------------
# The page ships "let media=[{...}]" and the download form names which entry is
# selected. That entry holds Zipped (the download size in KB, exactly the number
# the page renders as e.g. "2.39 GB") and GoodTitle, a base64 romset filename --
# the value the served id="data-good-title" cell is empty until JS fills it in.
my ($dlrow) = $h =~ m{<tr\b[^>]*\bid=["\x27]dl-row["\x27].*?</tr>}is ? ($&) : ("");
my ($mediaid) = $dlrow =~ m{name=["\x27]mediaId["\x27][^>]*\bvalue=["\x27](\d+)}i;
my ($kb, $release) = ("", "");
if (defined $mediaid && $mediaid ne "") {
  if ($h =~ m{"ID"\s*:\s*\Q$mediaid\E\D.{0,4000}?"Zipped"\s*:\s*"?(\d+)}s)     { $kb = $1 }
  if ($h =~ m{"ID"\s*:\s*\Q$mediaid\E\D.{0,4000}?"GoodTitle"\s*:\s*"([^"]*)"}s) {
    my $d = eval { MIME::Base64::decode_base64($1) };
    if (defined $d && $d =~ /^[\x20-\x7e]+$/) { $release = $d }
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
if (!@regions && ($f{region} || "") ne "" && $f{region} ne "?") { push @regions, $f{region} }
my %rs; my @ru = grep { !$rs{lc $_}++ } @regions;
my $region = join("+", @ru);
$region = "Unknown" if $region eq "";

# --- rating ---------------------------------------------------------------
my ($rating, $votes) = ("", "");
if (($f{overall} || "") =~ /([\d.]+)\s*(?:\(\s*(\d+)\s*votes?\s*\))?/) { $rating = $1; $votes = defined $2 ? $2 : "" }

# --- size -----------------------------------------------------------------
# The size shown next to the Download button is rendered by JavaScript, so it
# is looked for in this order:
#   1. inside the <tr id="dl-row"> download box (in case it is server-side)
#   2. in the JS data the page hands to setMediaId() -- a size string with a
#      unit, or a raw byte count
#   3. the old textual fallbacks, clearly labelled in the audit trail
# Scoping matters: an unscoped search happily returns the "Cart size" row.
my $SZ = qr{([\d]+(?:\.\d+)?)\s*(?:&nbsp;|\s)*\b(TB|GB|MB|KB)\b};
my ($size, $unit, $src, $bytes) = ("", "", "none", "");

# Zipped is exact; the rendered "2.39 GB" is that value rounded to 2 decimals,
# so preferring it keeps the grand total from drifting over thousands of rows.
if ($kb ne "") { ($size,$unit,$src) = ($kb,"KB","js-zipped") }
if ($size eq "" && $dlrow ne "" && $dlrow =~ m{$SZ}is) { ($size,$unit,$src) = ($1,$2,"dl-row") }

if ($size eq "") {
  # JS payload: pick the entry for the preferred format when it is labelled,
  # otherwise the first size-looking value.
  my @scripts = ($h =~ m{<script\b[^>]*>(.*?)</script>}gis);
  my $js = join(" ", @scripts);
  if ($js =~ m{\Q$prefer\E.{0,200}?["\x27]?(?:size|Size|SIZE)["\x27]?\s*[:=]\s*["\x27]?$SZ}is) {
    ($size,$unit,$src) = ($1,$2,"js-format-size");
  } elsif ($js =~ m{["\x27]?(?:size|Size|SIZE)["\x27]?\s*[:=]\s*["\x27]$SZ}is) {
    ($size,$unit,$src) = ($1,$2,"js-size-string");
  } elsif ($js =~ m{["\x27]?(?:size|Size|SIZE|bytes|Bytes)["\x27]?\s*[:=]\s*["\x27]?(\d{6,})}is) {
    ($bytes,$src) = ($1,"js-size-bytes");
  }
}

if ($size eq "" && $bytes eq "" && $h =~ m{\.\Q$prefer\E\b.{0,800}?$SZ}is) {
  ($size,$unit,$src) = ($1,$2,"format-label");
}
if ($size eq "" && $bytes eq "") {
  my @m;
  while ($h =~ m{$SZ}gis) { push @m, [$1,$2] }
  if (@m) { ($size,$unit) = @{$m[-1]}; $src = "last-on-page-UNRELIABLE" }
}

my $gb = 0;
if ($bytes ne "") {
  $gb = $bytes / (1024 * 1024 * 1024);
} elsif ($size ne "") {
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

# Clean the fields that come with decoration attached: the CRC cell carries a
# "More..." link, Verified carries a warning glyph, Version can still hold a
# list if the select markup changes.
my $crc = $f{crc} || "";
$crc = $1 if $crc =~ /\b([0-9a-fA-F]{8})\b/;
my $verified = $f{verified} || "";
$verified = $verified =~ /(\d{4}-\d{2}-\d{2})/ ? $1 : "";

my $version = $f{version} || "";
$version = $1 if $version =~ /^\s*(\d+(?:\.\d+)*)/;
my $vkey = 0;
if ($version =~ /^(\d+)(?:\.(\d+))?/) { $vkey = $1 * 1000 + (defined $2 ? $2 : 0) }

sub cell { my $s = shift; $s = "" unless defined $s; $s =~ s/[\t\r\n]+/ /g; $s =~ s/\s+/ /g; $s =~ s/^ | $//g; return $s }

print join("\t", map { cell($_) }
  $norm, $prio, $vkey, $gb, $id,
  $name, $region, $version,
  ($f{year} || ""), ($f{publisher} || ""), ($f{players} || ""),
  ($f{serial} || ""), $crc, $rating, $votes,
  $release, $format, $verified, $src), "\n";
'

TO_CSV_PL='
use strict; use warnings;
sub csvq { my $s = shift; $s = "" unless defined $s; $s =~ s/"/""/g; return "\"$s\"" }
print join(",", map { csvq($_) } qw(
  name region version year publisher players serial crc rating votes
  release_name format size_gb size_source verified vault_id url
  duplicates_dropped)), "\n";
while (my $l = <STDIN>) {
  chomp $l;
  my @c = split /\t/, $l, -1;
  next unless @c >= 19;
  my ($gb,$id,$name,$region,$ver,$year,$pub,$players,$serial,$crc,$rating,$votes,$rel,$fmt,$verified,$src) =
     ($c[3],$c[4],$c[5],$c[6],$c[7],$c[8],$c[9],$c[10],$c[11],$c[12],$c[13],$c[14],$c[15],$c[16],$c[17],$c[18]);
  my $dropped = defined $c[19] ? $c[19] : "";
  $gb = sprintf("%.2f", $gb || 0);
  print join(",", map { csvq($_) }
    $name, $region, $ver, $year, $pub, $players, $serial, $crc, $rating, $votes,
    $rel, $fmt, $gb, $src, $verified, $id, "https://vimm.net/vault/$id", $dropped), "\n";
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
    --filters)            USE_FILTERS=1; shift ;;
    --plain)              USE_FILTERS=0; shift ;;
    --print-url)          PRINT_URL="$2"; shift 2 ;;
    --refresh)            REFRESH=1; shift ;;
    --total-row)          TOTAL_ROW=1; shift ;;
    --self-test)          SELF_TEST=1; shift ;;
    -v|--verbose)         VERBOSE=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

if [ -n "$PRINT_URL" ]; then
  section_url "$PRINT_URL"
  printf '\n'
  exit 0
fi

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
# candidates.tsv: norm, rank, id, name, region, version -- rank 1 is the
# preferred regional variant of that title, 2 the next best, and so on.
build_candidates() {
  perl -e "$PARSE_INDEX_PL" <"$WORK/index.tsv" \
    | LC_ALL=C sort -t "$(printf '\t')" -k1,1 -k2,2n -k3,3nr -k4,4n \
    | awk -F'\t' -v OFS='\t' '
        { if ($1 != cur) { cur = $1; r = 0 } r++
          print $1, r, $4, $5, $6, $7 }
      ' >"$WORK/candidates.tsv"
}

# fetch_ids FILE -- download the detail page of every id in FILE (skips cached)
fetch_ids() {
  _src="$1"
  : >"$WORK/todo.txt"
  _need=0
  while read -r id; do
    [ -n "$id" ] || continue
    if [ ! -s "$CACHE/detail/$id.html" ] || [ "$REFRESH" -eq 1 ]; then
      printf '%s\n' "$id" >>"$WORK/todo.txt"; _need=$((_need + 1))
    fi
  done <"$_src"
  _have=$(( $(wc -l <"$_src" | tr -d ' ') - _need ))
  printf '%s already cached, %s to download\n' "$_have" "$_need" >&2
  [ "$_need" -gt 0 ] || return 0

  if [ "$JOBS" -gt 1 ]; then
    xargs -n1 -P "$JOBS" "$SELF" --fetch-one <"$WORK/todo.txt"
  else
    _i=0
    while read -r id; do
      _i=$((_i + 1))
      printf '\r  fetching %s/%s (id %s)   ' "$_i" "$_need" "$id" >&2
      "$SELF" --fetch-one "$id"
    done <"$WORK/todo.txt"
    printf '\n' >&2
  fi
}

# Fetch rank-1 candidates; if a title'\''s page is missing (404, or the fetch gave
# up), fall back to its next-best regional variant rather than losing the title.
resolve_winners() {
  : >"$WORK/resolved.tsv"
  _round=1
  while [ "$_round" -le 3 ]; do
    awk -F'\t' -v r="$_round" -v rf="$WORK/resolved.tsv" '
      FILENAME == rf { res[$1] = 1; next }
      $2 == r && !($1 in res) { print $3 }
    ' "$WORK/resolved.tsv" "$WORK/candidates.tsv" >"$WORK/try.txt"
    [ -s "$WORK/try.txt" ] || break
    [ "$_round" -eq 1 ] || printf 'retrying %s title(s) with the next-best region\n' \
      "$(wc -l <"$WORK/try.txt" | tr -d ' ')" >&2

    fetch_ids "$WORK/try.txt"

    : >"$WORK/ok.txt"
    while read -r id; do
      [ -s "$CACHE/detail/$id.html" ] && printf '%s\n' "$id" >>"$WORK/ok.txt"
    done <"$WORK/try.txt"
    awk -F'\t' -v OFS='\t' -v okf="$WORK/ok.txt" '
      FILENAME == okf { ok[$1] = 1; next }
      ok[$3]          { print $1, $3 }
    ' "$WORK/ok.txt" "$WORK/candidates.tsv" >>"$WORK/resolved.tsv"

    _round=$((_round + 1))
  done

  # what each winner beat, for the duplicates_dropped column
  awk -F'\t' -v OFS='\t' -v rf="$WORK/resolved.tsv" '
    FILENAME == rf { win[$1] = $2; next }
    !($1 in win) { next }
    $3 == win[$1] { next }
    {
      d = $4 " (" $5 ")"
      if ($6 != "") d = d " v" $6
      d = d " #" $3
      k = win[$1]
      drop[k] = (drop[k] == "" ? d : drop[k] " | " d)
    }
    END { for (k in drop) print k, drop[k] }
  ' "$WORK/resolved.tsv" "$WORK/candidates.tsv" >"$WORK/dropped.tsv"
}

# Attach the dropped-variant list to the parsed winner rows.
join_dropped() {
  LC_ALL=C sort -t "$(printf '\t')" -k1,1 -k5,5n "$WORK/rows.tsv" >"$WORK/rows.sorted.tsv"
  awk -F'\t' -v OFS='\t' -v df="$WORK/dropped.tsv" '
    FILENAME == df { dr[$1] = $2; next }
    { print $0, ($5 in dr ? dr[$5] : "") }
  ' "$WORK/dropped.tsv" "$WORK/rows.sorted.tsv" >"$WORK/final.tsv"
}

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

  # Fixtures mirror the markup the live site actually serves, as captured by
  # probe.sh: a hidden decoy link before the real one, a space after href=,
  # lowercase flag files with a title attribute, the console nav <h2> that must
  # not be mistaken for the title, a three-column label/spacer/value info
  # table, an empty JS-populated data-good-title, and the size inside
  # <tr id="dl-row"> (id 105 instead carries it in the JS payload).
  make_detail() { # id name region version size [kb]
    _dl="<td style=\"width:33%; text-align:center\" id=\"dl_size\">$5</td>"
    if [ -n "${6:-}" ]; then
      # the real payload: base64 GoodTitle, exact Zipped in KB, nested GoodDate
      _b64=$(printf '%s (%s) (En,Fr).iso' "$2" "$3" | base64 | tr -d '\n')
      _js="<script>let media=[{\"ID\":$1,\"GoodDate\":{\"date\":\"2026-08-04 12:54:58.000000\",\"timezone_type\":3},\"GoodTitle\":\"$_b64\",\"Serial\":\"RVL-RGQE-USA\",\"SortOrder\":1,\"Version\":\"$4\",\"Zipped\":\"$6\",\"AltZipped\":\"1600938\"}];</script>"
    else
      _js=""
    fi
    cat >"$CACHE/detail/$1.html" <<EOF
<html><head>
<meta property="og:title" content="$2">
<meta property="og:description" content="Download &quot;$2&quot; ($3) for the Wii">
<title>The Vault: $2 (Wii)</title>
$_js
</head><body>
<div class="menu"><h2>Nintendo</h2><a href="/vault/Wii">Wii</a></div>
<table>
<tr><td style="width:0px">Region</td><td style="width:15px"></td><td><img src="/images/flags/$(printf '%s' "$3" | tr 'A-Z' 'a-z').png" class="flag" title="$3"></td></tr>
<tr><td style="width:0px">Players</td><td style="width:15px"></td><td> 2 </td></tr>
<tr><td>Year</td><td></td><td>2009</td></tr>
<tr><td>Publisher</td><td></td><td>Atari SA</td></tr>
<tr><td style="white-space:nowrap">Serial #</td><td></td><td>RVL-RGQE-USA</td></tr>
<tr><td>Graphics</td><td></td><td>8.14</td></tr>
<tr><td>Overall</td><td></td><td>8.9&nbsp;<span style="font-size:90%">(21 votes)</span>&nbsp;<div style="float:right"><a href="/vault/?p=rating&amp;id=$1">Rate it!</a></div></td></tr>
<tr><td style="font-style:italic" colspan="3" id="data-good-title"> </td></tr>
<tr><td>CRC</td><td></td><td>a6539a7a&nbsp;<div style="float:right"><a href="#">More...</a></div></td></tr>
<tr><td>Verified</td><td></td><td>2026-08-04 &#x26a0;</td></tr>
<tr><td>Format</td><td></td><td><select id="dl_format"><option value="0" selected>.wbfs</option><option value="1">.rvz</option></select></td></tr>
<tr><td>Version</td><td></td><td><select id="dl_version"><option>1.0</option><option selected>$4</option></select></td></tr>
<tr id="dl-row"><td style="width:33%"></td><td style="width:33%"><form action="//dl3.vimm.net/" method="POST" id="dl_form"><input type="hidden" name="mediaId" value="$1"><input type="submit" value="Download"></form></td>$_dl</tr>
</table></body></html>
EOF
  }

  make_detail 101 "Ghostbusters: The Video Game" Europe 1.0 "2.75 GB"
  make_detail 102 "Ghostbusters: The Video Game" USA   1.1 "2.81 GB"
  make_detail 103 "Ghost Squad"                  Japan 1.0 "512 MB"
  make_detail 104 "Ghost Squad"                  Europe 1.0 "600 MB"
  # 1048576 KB is exactly 1 GB -- carries the JS payload as well
  make_detail 105 "Geon Cube"                    USA   1.0 "1.00 GB" 1048576
  printf '101\n102\n103\n104\n105\n' >"$WORK/ids.txt"

  # List-page fixture: note the decoy anchor and the "href= " spacing.
  cat >"$CACHE/list.html" <<'EOF'
<table><tr><th>Title</th><th>Region</th><th>Version</th></tr>
<tr><td style="width:auto"><a href="/vault/999999" style="display:none">9</a><a href= "/vault/101">Ghostbusters: The Video Game</a></td><td style="width:65px; text-align:center"><div style="display:flex"><img src="/images/flags/europe.png" class="flag" title="Europe"></div></td><td style="width:85px; text-align:center">1.0</td><td style="width:110px">2026-08-04</td></tr>
<tr><td style="width:auto"><a href="/vault/999999" style="display:none">9</a><a href= "/vault/103">Ghost Squad</a></td><td style="width:65px; text-align:center"><div style="display:flex"><img src="/images/flags/japan.png" class="flag" title="Japan"></div></td><td style="width:85px; text-align:center">1.0</td><td style="width:110px">2026-08-04</td></tr>
<tr><td style="width:auto"><a href="/vault/999999" style="display:none">9</a><a href= "/vault/106">Girls Life: Sleepover Party</a></td><td style="width:65px; text-align:center"><div style="display:flex"><img src="/images/flags/australia.png" class="flag" title="Australia"><img src="/images/flags/europe.png" class="flag" title="Europe"></div></td><td style="width:85px; text-align:center">1.0</td><td style="width:110px">2026-08-04</td></tr>
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
  chk "size GB"          "$(head -1 "$WORK/rows.tsv" | cut -f4)" "2.7500"
  chk "size from dl-row" "$(head -1 "$WORK/rows.tsv" | cut -f19)" "dl-row"
  chk "size MB->GB"      "$(awk -F'\t' '$5==103{print $4}' "$WORK/rows.tsv")" "0.5000"
  chk "size from JS KB"  "$(awk -F'\t' '$5==105{print $4 "/" $19}' "$WORK/rows.tsv")" "1.0000/js-zipped"
  chk "release from b64" "$(awk -F'\t' '$5==105{print $16}' "$WORK/rows.tsv")" "Geon Cube (USA) (En,Fr).iso"
  chk "crc cleaned"      "$(head -1 "$WORK/rows.tsv" | cut -f13)" "a6539a7a"
  chk "verified cleaned" "$(head -1 "$WORK/rows.tsv" | cut -f18)" "2026-08-04"
  chk "version from sel" "$(head -1 "$WORK/rows.tsv" | cut -f8)" "1.0"
  chk "format from sel"  "$(head -1 "$WORK/rows.tsv" | cut -f17)" "wbfs"
  # the console nav heading must not win over og:title
  chk "nav h2 ignored"   "$(awk -F'\t' '$6 ~ /Nintendo/{print "leaked"}' "$WORK/rows.tsv")" ""

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
  chk "csv release col"  "$(csvfield "$OUT" 2 11)" "Geon Cube (USA) (En,Fr).iso"
  chk "csv format col"   "$(csvfield "$OUT" 4 12)" "wbfs"
  chk "csv size col"     "$(csvfield "$OUT" 4 13)" "2.75"
  chk "csv size source"  "$(csvfield "$OUT" 4 14)" "dl-row"
  chk "csv verified col" "$(csvfield "$OUT" 4 15)" "2026-08-04"
  chk "csv url col"      "$(csvfield "$OUT" 4 17)" "https://vimm.net/vault/101"
  chk "csv dropped col"  "$(csvfield "$OUT" 4 18)" "Ghostbusters: The Video Game (USA) v1.1 #102"
  # 2.75 + 0.5859375 (600MB) + 1.00
  chk "total sum"        "$(awk -F'\t' '{s+=$4} END{printf "%.2f", s}' "$WORK/final.tsv")" "4.34"

  KEEP_DUPES=1; dedup_rows
  chk "keep-duplicates"  "$(wc -l <"$WORK/final.tsv" | tr -d ' ')" "5"
  KEEP_DUPES=0

  # --- list-level dedup: pick winners before fetching any detail page --------
  # 101/102 are the same title (Europe v1.0 vs USA v1.1), 103/104 likewise.
  printf '%s\n' \
    "101	Ghostbusters: The Video Game	Europe	1.0" \
    "102	Ghostbusters: The Video Game	USA	1.1" \
    "103	Ghost Squad	Japan	1.0" \
    "104	Ghost Squad	Australia+Europe	1.0" \
    "105	Geon Cube	USA	1.0" >"$WORK/index.tsv"
  build_candidates
  chk "cand rows"        "$(wc -l <"$WORK/candidates.tsv" | tr -d ' ')" "5"
  chk "cand titles"      "$(cut -f1 "$WORK/candidates.tsv" | uniq | wc -l | tr -d ' ')" "3"
  chk "EU is rank 1"     "$(awk -F'\t' '$1 ~ /^ghostbusters/ && $2==1 {print $3}' "$WORK/candidates.tsv")" "101"
  chk "US is rank 2"     "$(awk -F'\t' '$1 ~ /^ghostbusters/ && $2==2 {print $3}' "$WORK/candidates.tsv")" "102"
  chk "multiflag rank 1" "$(awk -F'\t' '$1=="ghost squad" && $2==1 {print $3}' "$WORK/candidates.tsv")" "104"
  # only the 3 winners would be downloaded, not all 5 entries
  chk "winners only"     "$(awk -F'\t' '$2==1{print $3}' "$WORK/candidates.tsv" | sort -n | tr '\n' ' ')" "101 104 105 "

  # winner 101's page exists, so resolve_winners must settle on it in round 1
  JOBS=1; REFRESH=0
  resolve_winners >/dev/null 2>&1
  chk "resolved count"   "$(wc -l <"$WORK/resolved.tsv" | tr -d ' ')" "3"
  chk "dropped recorded2" "$(awk -F'\t' '$1==101{print $2}' "$WORK/dropped.tsv")" \
                          "Ghostbusters: The Video Game (USA) v1.1 #102"

  # fallback: winner 106 has no cached page, so rank 2 (id 105) must win
  printf '%s\n' \
    "106	Geon Cube	Europe	1.0" \
    "105	Geon Cube	USA	1.0" >"$WORK/index.tsv"
  build_candidates
  DELAY=0; MAX_RETRIES=1
  resolve_winners >/dev/null 2>&1
  chk "missing winner"   "$(awk -F'\t' '$1=="geon cube"{print $2}' "$WORK/resolved.tsv")" "105"

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

entries=$(wc -l <"$WORK/index.tsv" | tr -d ' ')
if [ "$entries" -eq 0 ]; then
  if [ -z "$(ls -A "$CACHE/list" 2>/dev/null)" ]; then
    die "no list page could be downloaded at all -- vimm.net was unreachable from
       this machine (network down, DNS, a VPN/proxy, or Vimm blocking the request).
       Check with: curl -sI https://vimm.net/vault/Wii | head -1"
  fi
  die "list pages downloaded but no games parsed -- the markup has probably changed.
       Inspect $CACHE/list/*.html and adjust PARSE_LIST_PL."
fi

export VW_CACHE="$CACHE" VW_DELAY="$DELAY" VW_VERBOSE="$VERBOSE" \
       VW_RETRIES="$MAX_RETRIES" VW_REFRESH="$REFRESH"

# ---------------------------------------------------------------------------
# Stage 2: pick the regional winners, then fetch only their detail pages
# ---------------------------------------------------------------------------
if [ "$KEEP_DUPES" -eq 1 ]; then
  cut -f1 "$WORK/index.tsv" | LC_ALL=C sort -u -n >"$WORK/ids.all"
else
  build_candidates
  titles=$(cut -f1 "$WORK/candidates.tsv" | LC_ALL=C uniq | wc -l | tr -d ' ')
  printf '%s list entries -> %s distinct titles (%s regional duplicates skipped)\n' \
    "$entries" "$titles" "$((entries - titles))" >&2
  awk -F'\t' '$2 == 1 { print $3 }' "$WORK/candidates.tsv" \
    | LC_ALL=C sort -u -n >"$WORK/ids.all"
fi

if [ "$LIMIT" -gt 0 ]; then
  head -"$LIMIT" "$WORK/ids.all" >"$WORK/ids.txt"
else
  cp "$WORK/ids.all" "$WORK/ids.txt"
fi
printf '%s detail pages to fetch\n' "$(wc -l <"$WORK/ids.txt" | tr -d ' ')" >&2

if [ "$KEEP_DUPES" -eq 1 ] || [ "$LIMIT" -gt 0 ]; then
  # --limit takes a flat slice, so the multi-round winner fallback does not apply
  fetch_ids "$WORK/ids.txt"
else
  resolve_winners
  cut -f2 "$WORK/resolved.tsv" | LC_ALL=C sort -u -n >"$WORK/ids.txt"
fi

# ---------------------------------------------------------------------------
# Stage 3-5: parse, attach dropped variants, CSV, total
# ---------------------------------------------------------------------------
parse_details
[ -s "$WORK/rows.tsv" ] || die "nothing parsed -- inspect $CACHE/detail/*.html"
# audit trail: size_gb, id, name, which rule found the size
cut -f4,5,6,19 "$WORK/rows.tsv" >"$WORK/size-source.tsv"

if [ "$KEEP_DUPES" -eq 1 ] || [ "$LIMIT" -gt 0 ]; then
  dedup_rows          # nothing was pre-deduped, fall back to row-level dedup
else
  join_dropped
fi
write_csv
print_summary

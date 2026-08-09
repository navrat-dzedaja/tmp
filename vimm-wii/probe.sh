#!/bin/bash
#
# probe.sh URL [KEEPFILE] -- fetch a Vault page and describe its structure, so
# the selectors in vimm-wii-catalog.sh can be checked against reality instead
# of guessed at.
#
# Prints: HTTP status, size, <title>, element counts, and excerpts around the
# game links. If no game links are found it dumps the page's visible text
# instead, which is what you want to see when the server answers with a
# challenge page, an error, or an empty result set.

set -u

URL="${1:?usage: probe.sh URL [KEEPFILE]}"
OUT="${2:-${TMPDIR:-/tmp}/probe.$$.html}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

code=$(curl -sSL --compressed -A "$UA" \
            -H 'Accept: text/html,application/xhtml+xml' \
            -H 'Accept-Language: en-US,en;q=0.9' \
            --max-time 60 -o "$OUT" -w '%{http_code}' "$URL" 2>&1) || true

echo "================================================================"
echo "URL   : $URL"
echo "HTTP  : $code    bytes: $(wc -c <"$OUT" 2>/dev/null | tr -d ' ')"

perl -e '
local $/; my $h = <STDIN>; $h = "" unless defined $h;
my $flat = $h; $flat =~ s/\r?\n/ /g;

sub count { my $re = shift; my $n = 0; $n++ while $flat =~ /$re/g; return $n }

my $title = ($h =~ m{<title>(.*?)</title>}is) ? $1 : "(none)";
$title =~ s/\s+/ /g;
print "title : $title\n";
printf "counts: table=%d tr=%d td=%d img=%d a=%d  /vault/N=%d  select=%d\n",
  count(qr{<table\b}i), count(qr{<tr\b}i), count(qr{<td\b}i),
  count(qr{<img\b}i), count(qr{<a\b}i), count(qr{/vault/\d+}i),
  count(qr{<select\b}i);

if ($flat =~ m{<meta[^>]+og:title[^>]+content=["\x27]([^"\x27]+)}i) {
  print "og:title: $1\n";
}

# List pages: the rows that hold a real game link.
my $rows = 0;
for my $r (split /<tr\b/i, $flat) {
  next unless $r =~ m{/vault/\d+}i && $r =~ m{<td\b}i;
  next if $r =~ m{<!DOCTYPE}i;
  print "\n[list row] <tr", substr($r, 0, 460), "\n";
  last if ++$rows >= 2;
}

# Detail pages: the info rows, the download box, and the JS that fills it in.
for my $label ("Region", "Version", "Format", "Serial") {
  for my $r (split /<tr\b/i, $flat) {
    if ($r =~ m{<td\b[^>]*>\s*\Q$label\E}i) {
      print "\n[$label row] <tr", substr($r, 0, 300), "\n";
      last;
    }
  }
}
if ($flat =~ m{(<tr\b[^>]*\bid=["\x27]dl-row["\x27].*?</tr>)}is) {
  print "\n[dl-row] ", substr($1, 0, 1200), "\n";
}
my @scripts = ($flat =~ m{<script\b[^>]*>(.*?)</script>}gis);
my $shown = 0;
for my $s (@scripts) {
  next unless $s =~ /media|mediaId|size|Size|GB|MB/;
  next if $s =~ /gtag|dataLayer|googletag/;
  print "\n[script ", ++$shown, "] ", substr($s, 0, 1200), "\n";
  last if $shown >= 3;
}
print "\n(no <script> mentioned media/size)\n" unless $shown;

my @links = ($flat =~ m{(/vault/\d+)}gi);
unless (@links) {
  print "\nNO GAME LINKS FOUND -- visible text of the page follows\n";
  my $t = $flat;
  $t =~ s{<script\b.*?</script>}{ }gis;
  $t =~ s{<style\b.*?</style>}{ }gis;
  $t =~ s/<[^>]*>/ /g;
  $t =~ s/&nbsp;/ /g; $t =~ s/&amp;/&/g;
  $t =~ s/\s+/ /g;
  print substr($t, 0, 1500), "\n";
}
' <"$OUT"

echo "saved : $OUT"

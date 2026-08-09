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

my @links = ($flat =~ m{(/vault/\d+)}gi);
if (@links) {
  print "\n--- 3 excerpts around game links (400 chars each) ---\n";
  my $n = 0;
  while ($flat =~ m{(.{0,120}/vault/\d+.{0,280})}gi) {
    print "[$n] $1\n\n";
    last if ++$n >= 3;
  }
  print "--- first 2 img tags ---\n";
  $n = 0;
  while ($flat =~ m{(<img\b[^>]*>)}gi) { print "$1\n"; last if ++$n >= 2 }
} else {
  print "\nNO GAME LINKS FOUND -- visible text of the page follows\n";
  my $t = $flat;
  $t =~ s{<script\b.*?</script>}{ }gis;
  $t =~ s{<style\b.*?</style>}{ }gis;
  $t =~ s/<[^>]*>/ /g;
  $t =~ s/&nbsp;/ /g; $t =~ s/&amp;/&/g;
  $t =~ s/\s+/ /g;
  print substr($t, 0, 1500), "\n";
}

# Download box: the size we care about lives here.
if ($flat =~ m{(.{0,500}Download.{0,500})}is) {
  print "\n--- around the word Download ---\n$1\n";
}
' <"$OUT"

echo "saved : $OUT"

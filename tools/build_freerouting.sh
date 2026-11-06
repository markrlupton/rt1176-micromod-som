#!/usr/bin/env bash
# Build Freerouting v1.4.4 from its official source without Maven/Gradle (blocked in some sandboxes).
# log4j, JavaHelp and the generated Constants class are replaced by tiny stubs in tools/freerouting_stubs/.
# Output: tools/bin/freerouting-1.4.4.jar (git-ignored). Run headless with: xvfb-run java -jar ... -de x.dsn -do x.ses -mp 20
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; B="$(mktemp -d)"
git clone -q --depth 1 --branch v1.4.4 https://github.com/freerouting/freerouting "$B/fr"
find "$B/fr/src/main/java" "$HERE/freerouting_stubs" -name '*.java' > "$B/srcs.txt"
mkdir -p "$B/out" "$HERE/bin"
javac -nowarn -encoding UTF-8 -d "$B/out" @"$B/srcs.txt"
cp -r "$B/fr/src/main/resources/"* "$B/out/"
printf 'Main-Class: eu.mihosoft.freerouting.gui.MainApplication\n' > "$B/manifest.txt"
jar cfm "$HERE/bin/freerouting-1.4.4.jar" "$B/manifest.txt" -C "$B/out" .
echo "built $HERE/bin/freerouting-1.4.4.jar"

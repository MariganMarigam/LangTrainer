#!/bin/sh
# LangTrainer — install the AppImage into your own user account.
#
# No administrator rights are needed or used: everything lands under $HOME (or
# $XDG_DATA_HOME / $XDG_BIN_DIR when you have set them), and nothing is written
# outside your home directory. There is no background service and no third-party
# daemon — the app is a tray icon and nothing else.
#
# Usage:
#   ./install.sh                       uses an AppImage found next to this script
#   ./install.sh /path/to/Some.AppImage
#
# To undo:
#   ./uninstall.sh                     removes the app, keeps your words
#   ./uninstall.sh --purge             removes the app AND your words
#
# Exit codes: 0 success, 1 no AppImage found, 2 unexpected failure.

set -eu

APP_DIR_NAME="LangTrainer"
BIN_NAME="langtrainer"

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

# Same defaults the XDG Base Directory specification defines, written out longhand
# so the script behaves identically on a machine that never exports them.
XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
XDG_BIN_DIR=${XDG_BIN_DIR:-"$HOME/.local/bin"}

INSTALL_DIR="$XDG_DATA_HOME/$APP_DIR_NAME"
INSTALL_PATH="$INSTALL_DIR/$BIN_NAME"
APPLICATIONS_DIR="$XDG_DATA_HOME/applications"
DESKTOP_PATH="$APPLICATIONS_DIR/$BIN_NAME.desktop"
LINK_PATH="$XDG_BIN_DIR/$BIN_NAME"
ICON_DIR="$XDG_DATA_HOME/icons/hicolor/1024x1024/apps"
ICON_PATH="$ICON_DIR/$BIN_NAME.png"


die() {
    printf 'install.sh: %s\n' "$1" >&2
    exit "${2:-2}"
}


usage() {
    # Print the leading comment block (line 2 up to the first empty line) so the
    # help text can never drift out of sync with the header above it.
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}


# Print the first usable AppImage: the one named on the command line, else the
# first *.AppImage sitting next to this script. Returns 1 when there is none.
find_appimage() {
    if [ "$#" -ge 1 ] && [ -n "$1" ]; then
        printf '%s\n' "$1"
        return 0
    fi
    for candidate in "$SCRIPT_DIR"/*.AppImage; do
        if [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}


# Print the path of the 1024 px icon, or nothing when it cannot be found.
find_icon() {
    if [ -n "${LANGTRAINER_ICON:-}" ] && [ -f "$LANGTRAINER_ICON" ]; then
        printf '%s\n' "$LANGTRAINER_ICON"
        return 0
    fi
    for candidate in \
        "$SCRIPT_DIR/assets/icons/$BIN_NAME.png" \
        "$SCRIPT_DIR/$BIN_NAME.png"
    do
        if [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}


# A desktop Exec= value containing spaces has to be quoted, or the launcher
# splits it into two arguments and the app never starts.
quote_exec() {
    case "$1" in
        *[[:space:]]*) printf '"%s"' "$1" ;;
        *) printf '%s' "$1" ;;
    esac
}


case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
esac

SOURCE=$(find_appimage "$@") || die "no AppImage found. Pass one as an argument, e.g. ./install.sh LangTrainer-1.0.2-linux-x86_64.AppImage" 1
[ -f "$SOURCE" ] || die "not a file: $SOURCE" 1

printf 'Installing %s\n' "$SOURCE"
printf '      to: %s\n' "$INSTALL_PATH"

# An AppImage that lost its exec bit in transit cannot be run or copied usefully.
chmod +x "$SOURCE" 2>/dev/null || true

mkdir -p "$INSTALL_DIR" "$APPLICATIONS_DIR" "$XDG_BIN_DIR" "$ICON_DIR"

# `cp` (not `mv`): the downloaded AppImage is kept, so uninstalling does not
# have to put it back.
cp -f "$SOURCE" "$INSTALL_PATH"
chmod 755 "$INSTALL_PATH"

cat > "$DESKTOP_PATH" <<EOF
[Desktop Entry]
Type=Application
Name=LangTrainer
Comment=Learn foreign words through passive popups and 13 games
# Absolute on purpose. A relative Exec= is resolved against the desktop file's
# own directory, so "AppRun" only ever works from inside the unmounted image.
Exec=$(quote_exec "$INSTALL_PATH")
Icon=$BIN_NAME
Terminal=false
Categories=Education;Language;
StartupNotify=false
EOF

# Symlink rather than a second copy, so upgrading one file is enough.
ln -sf "$INSTALL_PATH" "$LINK_PATH"

if ICON_SOURCE=$(find_icon); then
    cp -f "$ICON_SOURCE" "$ICON_PATH"
    printf '   icon: %s\n' "$ICON_PATH"
else
    printf 'install.sh: no icon found next to this script; the menu entry will use a generic icon.\n' >&2
    printf 'install.sh: set LANGTRAINER_ICON=/path/to/langtrainer.png and re-run to install one.\n' >&2
fi

# Both helpers are optional and may be absent on a minimal desktop. Their
# failure is not our failure: the entry is already on disk and most launchers
# pick it up without a refreshed cache.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$XDG_DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

printf '\nLangTrainer is installed.\n\n'
printf '  Menu entry  : search "LangTrainer" in your application menu\n'
printf '  Binary      : %s\n' "$INSTALL_PATH"
printf '  Command line: %s\n' "$LINK_PATH"
printf '  Desktop file: %s\n' "$DESKTOP_PATH"
printf '  Your words  : %s (created on first run)\n\n' "$INSTALL_DIR/data"
printf 'To undo:\n'
printf '  ./uninstall.sh          remove the app, keep your words\n'
printf '  ./uninstall.sh --purge  remove the app AND your words\n'

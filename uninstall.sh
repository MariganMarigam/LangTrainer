#!/bin/sh
# LangTrainer — undo ./install.sh.
#
# This removes exactly what install.sh created: the menu entry, the command
# symlink, the installed binary and the icon.
#
# It does NOT delete your vocabulary by default. Your database lives in
#   ${XDG_DATA_HOME:-$HOME/.local/share}/LangTrainer/data/lang_trainer.db
# and that is the only copy of your work. Deleting it is irreversible, so it
# happens only when you ask for it explicitly:
#
#   ./uninstall.sh            remove the app, KEEP your words
#   ./uninstall.sh --purge    remove the app AND your words, permanently
#
# No administrator rights are needed or used; nothing outside your home
# directory is touched.
#
# Exit codes: 0 success, 2 bad usage.

set -eu

APP_DIR_NAME="LangTrainer"
BIN_NAME="langtrainer"

XDG_DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
XDG_BIN_DIR=${XDG_BIN_DIR:-"$HOME/.local/bin"}

INSTALL_DIR="$XDG_DATA_HOME/$APP_DIR_NAME"
INSTALL_PATH="$INSTALL_DIR/$BIN_NAME"
DESKTOP_PATH="$XDG_DATA_HOME/applications/$BIN_NAME.desktop"
LINK_PATH="$XDG_BIN_DIR/$BIN_NAME"
ICON_PATH="$XDG_DATA_HOME/icons/hicolor/1024x1024/apps/$BIN_NAME.png"

PURGE=0


usage() {
    # Print the leading comment block (line 2 up to the first empty line) so the
    # help text can never drift out of sync with the header above it.
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}


case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    --purge)
        PURGE=1
        ;;
    "")
        ;;
    *)
        printf 'uninstall.sh: unknown option: %s\n\n' "$1" >&2
        usage >&2
        exit 2
        ;;
esac

if [ -n "${2:-}" ]; then
    printf 'uninstall.sh: too many arguments\n\n' >&2
    usage >&2
    exit 2
fi

printf 'Uninstalling LangTrainer\n'

# Menu entry.
if [ -e "$DESKTOP_PATH" ]; then
    rm -f "$DESKTOP_PATH"
    printf '  removed menu entry: %s\n' "$DESKTOP_PATH"
fi

# Only ever remove the symlink itself. If something replaced it with a real
# file, that file is not ours to delete.
if [ -L "$LINK_PATH" ]; then
    rm -f "$LINK_PATH"
    printf '  removed symlink   : %s\n' "$LINK_PATH"
elif [ -e "$LINK_PATH" ]; then
    printf '  left alone (not a symlink): %s\n' "$LINK_PATH"
fi

# The installed binary.
if [ -f "$INSTALL_PATH" ]; then
    rm -f "$INSTALL_PATH"
    printf '  removed binary    : %s\n' "$INSTALL_PATH"
fi

# The icon.
if [ -e "$ICON_PATH" ]; then
    rm -f "$ICON_PATH"
    printf '  removed icon      : %s\n' "$ICON_PATH"
fi

if [ "$PURGE" -eq 1 ]; then
    # Belt and braces: only ever delete a directory whose name is exactly the
    # app's, and never the data home itself.
    if [ "$(basename "$INSTALL_DIR")" != "$APP_DIR_NAME" ]; then
        printf 'uninstall.sh: refusing to purge %s — unexpected directory name\n' "$INSTALL_DIR" >&2
        exit 2
    fi
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        printf '  PURGED data       : %s\n' "$INSTALL_DIR"
    fi
else
    # Prune the now-empty icon folder we created, but only if it is empty:
    # rmdir refuses otherwise, which is exactly the wanted behaviour.
    rmdir "$XDG_DATA_HOME/icons/hicolor/1024x1024/apps" 2>/dev/null || true
    rmdir "$XDG_DATA_HOME/icons/hicolor/1024x1024" 2>/dev/null || true
    rmdir "$XDG_DATA_HOME/icons/hicolor" 2>/dev/null || true
    rmdir "$XDG_DATA_HOME/icons" 2>/dev/null || true
fi

# Both helpers are optional; a missing one must not fail an uninstall.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$XDG_DATA_HOME/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$XDG_DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

printf '\n'
if [ "$PURGE" -eq 1 ]; then
    printf 'LangTrainer is gone, including your vocabulary. Nothing was kept.\n'
else
    printf 'LangTrainer is gone.\n\n'
    printf 'Your words are still here:\n  %s\n\n' "$INSTALL_DIR/data"
    printf 'Delete them for good with:\n  ./uninstall.sh --purge\n'
fi

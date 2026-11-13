{
  pkgs ? import <nixpkgs> { },
}:

let
  python = pkgs.python311;
  playwrightDriver = pkgs.playwright-driver;
in
pkgs.mkShell {
  name = "phone-ra";

  packages = [
    python
    python.pkgs.pip
    python.pkgs.virtualenv
    playwrightDriver.browsers # Chromium + ffmpeg, patched for NixOS
    pkgs.git
    pkgs.jq # for the version check in shellHook
  ];

  shellHook = ''
    # Use the nixpkgs-bundled Chromium instead of downloading one.
    export PLAYWRIGHT_BROWSERS_PATH=${playwrightDriver.browsers}
    export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

    # Create / activate a venv on entry.
    if [ ! -d .venv ]; then
      ${python}/bin/python -m venv .venv
    fi
    source .venv/bin/activate
    export PATH="$PWD/.venv/bin:$PATH"

    # Sanity: warn if pyproject's playwright pin doesn't match nixpkgs.
    if [ -f pyproject.toml ]; then
      PYPROJ_PW_VER="$(grep -oE 'playwright==[0-9.]+' pyproject.toml | head -1 | cut -d= -f3 || true)"
      NIX_PW_VER="$(nix eval --raw nixpkgs#playwright-driver.version 2>/dev/null || true)"
      if [ -n "$NIX_PW_VER" ] && [ -n "$PYPROJ_PW_VER" ] && [ "$PYPROJ_PW_VER" != "$NIX_PW_VER" ]; then
        echo "WARNING: pyproject pins playwright==$PYPROJ_PW_VER, nixpkgs ships $NIX_PW_VER" >&2
        echo "         Align pyproject.toml before running the pipeline." >&2
      fi
    fi

    echo "phone-ra dev shell ready"
    echo "  PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"
    echo "  Next: pip install -e '.[dev]'"
  '';
}

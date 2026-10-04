# Exact task-local ARM64 Linux Hono adapter; immutable public inputs only.
let
  input = builtins.fromJSON (builtins.readFile ./linux-hono/linux-inputs.json);
  pins = builtins.fromJSON (builtins.readFile ./pins.json);
  pkgs = import (builtins.storePath input.nixpkgs_source) { system = "aarch64-linux"; };
  tools = { inherit (pkgs) bash coreutils gzip stdenv; python = pkgs.python313;
    node = pkgs.nodejs_24; tar = pkgs.gnutar; sed = pkgs.gnused; };
  pnpmArchive = builtins.storePath (builtins.dirOf input.pnpm_archive) + "/" + builtins.baseNameOf input.pnpm_archive;
  pnpm = pkgs.runCommand "pnpmnix-linux-pnpm-12.6.0" { nativeBuildInputs = [ pkgs.gnutar pkgs.gzip pkgs.patchelf ]; } ''
    mkdir -p "$out/bin" extracted
    tar -xzf ${pnpmArchive} -C extracted
    cp extracted/package/pnpm "$out/bin/pnpm"
    chmod +x "$out/bin/pnpm"
    # Registry executable otherwise consumes Ubuntu's undeclared /lib loader.
    patchelf --set-interpreter ${pkgs.glibc}/lib/ld-linux-aarch64.so.1 \
      --set-rpath ${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.glibc}/lib "$out/bin/pnpm"
    test "$("$out/bin/pnpm" --version)" = 12.6.0
  '';
  onlyArchive = pkgs.fetchurl { url = pins.only-allow.url; hash = pins.only-allow.sha512_integrity; };
  whichArchive = pkgs.fetchurl { url = pins.which-pm-runs.url; hash = pins.which-pm-runs.sha512_integrity; };
  onlyAllow = pkgs.runCommand "pnpmnix-linux-only-allow-1.2.2" { nativeBuildInputs = [ pkgs.gnutar pkgs.gzip ]; } ''
    mkdir -p "$out/bin" "$out/lib/node_modules" only which
    tar -xzf ${onlyArchive} -C only
    tar -xzf ${whichArchive} -C which
    cp -R only/package "$out/lib/node_modules/only-allow"
    mkdir -p "$out/lib/node_modules/only-allow/node_modules"
    cp -R which/package "$out/lib/node_modules/only-allow/node_modules/which-pm-runs"
    cat > "$out/bin/only-allow" <<EOF
    #!${tools.bash}/bin/bash
    exec ${tools.node}/bin/node "$out/lib/node_modules/only-allow/bin.js" "\$@"
    EOF
    chmod +x "$out/bin/only-allow"
  '';
  caller = pkgs.runCommand "pnpmnix-linux-node-caller" { nativeBuildInputs = [ pkgs.stdenv.cc ]; } ''
    mkdir -p "$out/bin"
    cc -D_GNU_SOURCE -O2 -Wall -Wextra -Werror -DNODE_BIN='"${tools.node}/bin/node"' ${./scripts/node-caller-path.c} -o "$out/bin/node"
    "$out/bin/node" --version
  '';
  mk = name: script: specification: builtins.derivation {
    inherit name; system = "aarch64-linux"; builder = "${tools.bash}/bin/bash";
    args = [ "-e" "-c" ''
      source ${tools.stdenv}/setup
      export PATH="${pnpm}/bin:${caller}/bin:${tools.node}/bin:${onlyAllow}/bin:${pkgs.git}/bin:${tools.coreutils}/bin:${tools.sed}/bin:${tools.bash}/bin:$PATH"
      mkdir -p "$TMPDIR/config" "$TMPDIR/cache" "$TMPDIR/npm-cache"
      export XDG_CONFIG_HOME="$TMPDIR/config" XDG_CACHE_HOME="$TMPDIR/cache"
      export npm_config_cache="$TMPDIR/npm-cache" npm_config_prefix="${onlyAllow}" npm_config_offline=true
      export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 COREPACK_ENABLE_NETWORK=0 PNPM_DISABLE_SELF_UPDATE_CHECK=1
      export NODE_OPTIONS=--max-old-space-size=2048 GIT_CONFIG_NOSYSTEM=1
      ${tools.python}/bin/python3 ${script} "$specificationPath" "$out"
    '' ];
    passAsFile = [ "specification" ]; specification = builtins.toJSON specification;
    PATH = "${tools.coreutils}/bin:${tools.python}/bin:${tools.tar}/bin:${tools.gzip}/bin:${tools.bash}/bin";
    inherit (tools) stdenv;
    preferLocalBuild = true; allowSubstitutes = false;
    LC_ALL = "C"; TZ = "UTC"; PYTHONNOUSERSITE = "1"; PYTHONDONTWRITEBYTECODE = "1";
  };
  source = builtins.storePath input.hono_source;
  inputs = builtins.fromJSON (builtins.readFile ./local-hono/inputs.json);
  catalog = builtins.fromJSON (builtins.readFile ./local-hono/catalog.json);
  mapping = builtins.fromJSON (builtins.readFile ./local-hono/groups.json);
  validMap = builtins.sort builtins.lessThan (builtins.concatLists (builtins.attrValues mapping)) == builtins.attrNames catalog &&
    builtins.all (members: builtins.length members > 0 && builtins.length members <=64) (builtins.attrValues mapping);
  membership = builtins.listToAttrs (builtins.concatLists (builtins.map (name:
    builtins.map (id: { name = id; value = name; }) mapping.${name}
  ) (builtins.attrNames mapping)));
  acquisition = assert validMap; mk "pnpmnix-linux-hono-acquisition" ./linux-hono/scripts/acquire.py {
    archive_map = builtins.mapAttrs (id: row: {
      inherit (row) integrity originalUrl name version;
      archive = "${builtins.storePath input.groups.${membership.${id}}}/${row.storeName}";
    }) catalog;
  };
  prepared = mk "pnpmnix-linux-hono-prepared" ./linux-hono/scripts/prepare-hono.py {
    inherit source; source_hashes = inputs; archive_map = "${acquisition}/archive-map.json";
    pnpm = "${pnpm}/bin/pnpm"; node = "${tools.node}/bin/node"; bash = "${tools.bash}/bin/bash";
    adapter = ./scripts/adapter.cjs; trees = ./scripts/trees.py;
  };
  toolPaths = { pnpm = "${pnpm}/bin/pnpm"; node = "${tools.node}/bin/node"; bash = "${tools.bash}/bin/bash";
    git = "${pkgs.git}/bin/git"; launcher = "${caller}/bin/node"; only_allow = "${onlyAllow}/bin/only-allow"; };
in {
  bootstrap = pkgs.writeText "pnpmnix-linux-hono-bootstrap.json" (builtins.toJSON { tools = toolPaths; npm_prefix = onlyAllow; inherit source; profile = "hono"; });
  plan = { inherit source acquisition prepared; tools = toolPaths; };
  environments.hono = mk "pnpmnix-linux-environment-hono" ./linux-hono/scripts/bundle.py {
    profile = "hono"; inherit prepared source; store = "${prepared}/store"; hooks = [];
    deferred = "Exact ARM64 Linux Hono core flow only; other platforms/runtimes and frozen experiment return unqualified.";
    source_hashes = inputs; trees = ./scripts/trees.py; configuration_reader = ./scripts/configuration.py;
    tools = toolPaths; npm_prefix = onlyAllow;
  };
}

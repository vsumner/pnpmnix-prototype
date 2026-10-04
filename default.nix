let
  pins = builtins.fromJSON (builtins.readFile ./pins.json);
  nixpkgs = builtins.fetchTarball { url = pins.nixpkgs.url; sha256 = pins.nixpkgs.narHash; };
  pkgs = import nixpkgs { system = "aarch64-darwin"; };
  tools = {
    inherit (pkgs) bash coreutils gzip stdenv;
    tar = pkgs.gnutar; sed = pkgs.gnused; python = pkgs.python313; node = pkgs.nodejs_24;
    cc = pkgs.stdenv.cc; sdk = pkgs.apple-sdk_14;
  };
  fetch = name: url: hash: pkgs.fetchurl {
    inherit name url hash;
    curlOptsList = [ "--max-filesize" "536870912" "--max-time" "120" ];
    preferLocalBuild = true;
  };
  pnpmArchive = fetch "pnpm-native-12.6.0.tar.gz" pins.pnpm.url pins.pnpm.sha512_integrity;
  pnpm = pkgs.runCommand "pnpmnix-pnpm-12.6.0" { nativeBuildInputs = [ pkgs.gnutar pkgs.gzip ]; } ''
    mkdir -p "$out/bin" extracted
    tar -xzf ${pnpmArchive} -C extracted
    cp extracted/package/pnpm "$out/bin/pnpm"
    chmod +x "$out/bin/pnpm"
    test "$("$out/bin/pnpm" --version)" = 12.6.0
  '';
  onlyArchive = fetch "only-allow-1.2.2.tar.gz" pins.only-allow.url pins.only-allow.sha512_integrity;
  whichArchive = fetch "which-pm-runs-1.1.0.tar.gz" pins.which-pm-runs.url pins.which-pm-runs.sha512_integrity;
  onlyAllow = pkgs.runCommand "pnpmnix-only-allow-1.2.2" { nativeBuildInputs = [ pkgs.gnutar pkgs.gzip ]; } ''
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
  caller = pkgs.runCommand "pnpmnix-node-caller" { nativeBuildInputs = [ tools.cc tools.sdk ]; } ''
    mkdir -p "$out/bin"
    cc -O2 -Wall -Wextra -Werror -DNODE_BIN='"${tools.node}/bin/node"' ${./scripts/node-caller-path.c} -o "$out/bin/node"
    "$out/bin/node" --version
  '';
  sourceArchive = fetch "vite-source-10033218.tar.gz" pins.vite.url pins.vite.sha512_integrity;
  source = pkgs.runCommand "pnpmnix-vite-source-10033218" { nativeBuildInputs = [ pkgs.gnutar pkgs.gzip ]; } ''
    mkdir "$out"
    tar -xzf ${sourceArchive} --strip-components=1 -C "$out"
  '';
  mk = name: script: spec: builtins.derivation {
    inherit name;
    system = "aarch64-darwin";
    builder = "${tools.bash}/bin/bash";
    args = [ "-e" "-c" ''
      source ${tools.stdenv}/setup
      export PATH="${pnpm}/bin:${caller}/bin:${tools.node}/bin:${onlyAllow}/bin:${pkgs.git}/bin:${tools.coreutils}/bin:${tools.sed}/bin:${tools.bash}/bin:$PATH"
      mkdir -p "$TMPDIR/config" "$TMPDIR/cache" "$TMPDIR/npm-cache"
      export XDG_CONFIG_HOME="$TMPDIR/config" XDG_CACHE_HOME="$TMPDIR/cache"
      export npm_config_cache="$TMPDIR/npm-cache" npm_config_prefix="${onlyAllow}" npm_config_offline=true
      export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 COREPACK_ENABLE_NETWORK=0 PNPM_DISABLE_SELF_UPDATE_CHECK=1
      export NODE_OPTIONS=--max-old-space-size=6144 GIT_CONFIG_NOSYSTEM=1
      ${tools.python}/bin/python3 ${script} "$specificationPath" "$out"
    '' ];
    passAsFile = [ "specification" ];
    specification = builtins.toJSON spec;
    PATH = "${tools.coreutils}/bin:${tools.python}/bin:${tools.tar}/bin:${tools.gzip}/bin:${tools.bash}/bin";
    inherit (tools) stdenv;
    nativeBuildInputs = [ tools.cc tools.sdk ];
    preferLocalBuild = true;
    allowSubstitutes = false;
    LC_ALL = "C"; TZ = "UTC"; PYTHONNOUSERSITE = "1"; PYTHONDONTWRITEBYTECODE = "1";
  };
  common = {
    pnpm = "${pnpm}/bin/pnpm"; node = "${tools.node}/bin/node"; bash = "${tools.bash}/bin/bash";
    adapter = ./scripts/adapter.cjs;
  };
  catalog = builtins.fromJSON (builtins.readFile ./data/catalog.json);
  archives = builtins.mapAttrs (_: value: fetch value.storeName value.originalUrl value.integrity) catalog;
  mapping = builtins.fromJSON (builtins.readFile ./data/groups.json);
  validMap = builtins.sort builtins.lessThan (builtins.concatLists (builtins.attrValues mapping)) == builtins.attrNames catalog &&
    builtins.all (members: builtins.length members > 0 && builtins.length members <= 64) (builtins.attrValues mapping);
  groups = builtins.mapAttrs (name: members: mk "pnpmnix-archive-group-${name}" ./scripts/group.py {
    archive_group = builtins.listToAttrs (builtins.map (id: {
      name = id; value = catalog.${id} // { archive = archives.${id}; };
    }) members);
  }) mapping;
  membership = builtins.listToAttrs (builtins.concatLists (builtins.map (name:
    builtins.map (id: { name = id; value = name; }) mapping.${name}
  ) (builtins.attrNames mapping)));
  archiveMap = builtins.mapAttrs (id: value: {
    inherit (value) integrity originalUrl name version;
    archive = "${groups.${membership.${id}}}/${value.storeName}";
  }) catalog;
  vite = common // {
    inherit source;
    source_hashes = builtins.fromJSON (builtins.readFile ./data/source-inputs.json);
    node_launcher = "${caller}/bin/node"; only_allow = onlyAllow; git = "${pkgs.git}/bin/git";
    baseline_config = ./data/config.json; platform_check = ./scripts/platform-check.cjs;
    source_inventory = ./data/source-inventory.json; catalog = ./data/catalog.json;
    patcher = pkgs.writeText "pnpmnix-patch-shebangs" ''
      source ${tools.stdenv}/setup
      export PATH="${tools.node}/bin:${tools.bash}/bin:$PATH"
      patchShebangs --build "$@"
    '';
  };
  react = catalog."react@19.3.0";
  smokeGroup = mk "pnpmnix-smoke-archive-group" ./scripts/group.py {
    archive_group."react@19.3.0" = react // { archive = archives."react@19.3.0"; };
  };
  smokeAcquisition = mk "pnpmnix-smoke-acquisition" ./scripts/acquire.py {
    archive_map."react@19.3.0" = {
      inherit (react) integrity originalUrl name version;
      archive = "${smokeGroup}/${react.storeName}";
    };
  };
in assert validMap; rec {
  smoke = mk "pnpmnix-offline-smoke" ./scripts/smoke.py (common // { acquisition = smokeAcquisition; });
  missing = mk "pnpmnix-missing-control" ./scripts/negative.py (common // { acquisition = smokeAcquisition; mode = "missing"; });
  corrupt = mk "pnpmnix-corrupt-control" ./scripts/negative.py (common // { acquisition = smokeAcquisition; mode = "corrupt"; });
  smokeTests = [ smoke missing corrupt ];
  acquisition = mk "pnpmnix-vite-acquisition" ./scripts/acquire.py { archive_map = archiveMap; };
  materialized = mk "pnpmnix-vite-offline-store" ./scripts/materialize.py (vite // { inherit acquisition; });
  prepared = mk "pnpmnix-vite-prepared" ./scripts/prepare.py (vite // { acquired = "${materialized}/store"; });
  consumer = mk "pnpmnix-vite-consumer" ./scripts/consume.py (vite // {
    inherit prepared; acquired = "${materialized}/store"; patch = "${pkgs.patch}/bin/patch";
    graph_check = ./scripts/graph-check.cjs;
  });
  plan = {
    inherit mapping;
    group_outputs = builtins.mapAttrs (_: group: group.outPath) groups;
    tool_versions = { pnpm = "12.6.0"; node = tools.node.version; python = tools.python.version;
      git = pkgs.git.version; clang = tools.cc.version; sdk = tools.sdk.version; };
  };
}

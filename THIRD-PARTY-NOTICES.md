# Third-party inputs

The frozen Vite configuration, input hashes, and archive inventory describe the public Vite source pinned in pins.json. Its license follows. No Vite checkout, dependency archive, executable, package store, or Nixpkgs source tree is included. pnpm, Node, Nixpkgs packages, and registry dependencies are fetched separately under their respective licenses. This prototype does not relicense those dependencies.

## Vite

MIT License

Copyright (c) 2019-present, VoidZero Inc. and Vite contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Hono

The exact Hono configuration/input hashes and registry inventory describe the
official public revision pinned in `local-hono/source-pin.json`. The experiment
lockfile is derived from that revision by stock pnpm; the probe source files are
qualification code written for this prototype. No Hono checkout, dependency
archive, executable or package store is bundled. Those inputs are fetched
separately under their respective licenses. Hono's pinned source license follows.

MIT License

Copyright (c) 2021 - present, Yusuke Wada and Hono contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Linux Hono reuse path

The separate Linux adapter contains source code, exact public source/archive/NAR identities and a pathless qualification summary. Its required public Nix inputs and tools are acquired/imported separately; no archive, executable, package store, OS image or source checkout is distributed here. Existing Hono, pnpm, Node and Nixpkgs license boundaries above also apply. The public Nix store identities are immutable input references, not personal filesystem paths.

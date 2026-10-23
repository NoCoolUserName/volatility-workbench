# Adventure Easter egg

The game shares the existing CRT dialog and authenticated loopback transport. It has no case identifier, forensic API access, VolShell subprocess, job, report, AI, or volatility-mcp connection. It is launched through `Adventure.launch({edition:'select'})` in the page console. A visible development button appears only at `http://localhost/?adventure-dev=1`; no production click sequence is implemented.

## Included editions

**1977, 350 points.** The classic [NetBSD BSD Games port](https://github.com/NetBSD/src/tree/45137fe1cfe97f264940a616b3631bcaef1c3f6c/games/adventure) is pinned to commit `45137fe1cfe97f264940a616b3631bcaef1c3f6c`. Every C, header, and `glorkz` source file is downloaded by exact commit URL and checked against an individual SHA-256 in `scripts/build_bsd_adventure.py`. The port's source files carry the Regents of the University of California three-clause BSD notice, which is bundled verbatim. `glorkz` is the game-text database distributed as part of that port. It has no standalone license header; its redistribution is treated as part of the BSD port distribution, per the project owner's direction. The build makes narrow macOS compatibility and private-save changes and records them in the manifest. Both compiled `data.c` and the original `glorkz` bytes are present in the signed app. The 350-point save is separate from the 430-point save.

**1995, 430 points.**

Open Adventure 1.22 is Eric S. Raymond's C forward port of Crowther and Woods' Adventure 2.5 (1995). The build downloads the exact [1.22 archive](https://gitlab.com/esr/open-adventure/-/archive/1.22/open-adventure-1.22.tar.gz), checks SHA-256 `a40127c8296a5872ff69b53ecf4028797999f87cbc0735b9c379cecd1cb446f7`, and records upstream commit `e6160529e70a8c7a06b9a5f190d69aa35c4c62f5`. The archive's `COPYING` applies BSD-2-Clause; `adventure.yaml` explicitly carries `SPDX-License-Identifier: BSD-2-Clause`. A one-line macOS compatibility patch uses a mutable save-file pointer for restore. The generated C data is compiled into an ARM64 executable by the pinned recipe in `scripts/build_adventure.py`. PyYAML 6.0.3's macOS ARM64 wheel is hash pinned as a build-only dependency. The app includes the license text, source and game-data hashes, unsigned and signed executable hashes, and build receipt in `Contents/Resources/adventure` and `notices`. Package audit rejects missing or modified assets.

Each game uses a private save under the Workbench preferences directory: `adventure/advent-350.save` or `adventure/advent-430.save`. The manager accepts bounded commands, starts the binaries without a shell, captures bounded text through a PTY, and terminates its own process group on exit, timeout, or app shutdown. The 350-point port's save prompt is patched to use only the fixed private path, and the historical 45-minute resume delay is disabled. The 430-point port uses upstream autosave. Starting a new game deletes only the selected edition's save after explicit selection.

## Validation

CI runs synthetic Python session and HTTP routing tests, browser selection and restoration checks, the existing application regressions and package smoke, and an ARM64 macOS job that compiles and plays both pinned sources. The full signed app build remains a release step; CI's native game job uses ad hoc signatures only. No user evidence or local installation is read.

"""Build the pinned NetBSD 350-point Adventure port on ARM64 macOS."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess

COMMIT = "45137fe1cfe97f264940a616b3631bcaef1c3f6c"
BASE = f"https://raw.githubusercontent.com/NetBSD/src/{COMMIT}/games/adventure/"
SOURCES = {
    "crc.c": "32770eabe49d564bf9956b7ed354880b6a8789c0d781a18678e8e8ec87d45b57",
    "done.c": "323178aea00789ae08f9e985890a0e6b0c63350eb2756850e2e3dc67cafc763f",
    "extern.h": "d5259b194c1eb05487f44c12cbd9669ffeeba4636c6f6af06932f47fe99cddb8",
    "glorkz": "b564d874cf9edd190417268a9bf31dc720d3a60de0fe513f8df380b6bbbfec3e",
    "hdr.h": "14ad35fcb5977e4c023b9df68aecab75ae64fe1125e56f820053fd260a6a4f4b",
    "init.c": "7562bdd536acd94ac22dc83258584937758e519156a4f62beee6403c23c6f90f",
    "io.c": "1d2528e30469621c26be5d2e4629481cec42a06bb3f339841e10d5d548377343",
    "main.c": "f4330db4f42ae8fd8e7c35f8b0ea6e965636cef15b3069a440db9da09a2bad91",
    "save.c": "733dbd7f583e3bc8f94fe94431e7fdf4fee9e2368a1d29bf3014c3a7176f620a",
    "setup.c": "26a9ba13875883d0a572f32c0a484e523ecfff11de7e9a1467dc61ad0a0a2cb3",
    "subr.c": "892f62fa7d6bd6ceee307ad1a745e62818517f5d8040cb1ac12bb86e0f08d71f",
    "vocab.c": "3f3aef07c4d4b92b8ac3f7f8812f07dcf063f2c0a562ebbfb99dc8bb540d0b4c",
    "wizard.c": "6e1d32158d9109d26eb7c2cef955471100732d50d7ddff771e404174b7d399d1",
}
COMPAT = """#ifndef __noinline
#define __noinline __attribute__((noinline))
#endif
#ifndef __arraycount
#define __arraycount(a) (sizeof(a) / sizeof((a)[0]))
#endif
"""
FIXED_SAVE = """void
ciao(void)
{
    const char *name = getenv("VOLATILITY_ADVENTURE_SAVE");
    if (name == NULL || name[0] != '/') {
        fputs("Adventure save path is unavailable.\\n", stderr);
        return;
    }
    if (save(name) != 0)
        return;
    puts("Your adventure has been saved.");
    exit(0);
}
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(cache: Path, temporary: Path, resources: Path, fetch) -> dict:
    temporary.mkdir()
    for name, expected in SOURCES.items():
        shutil.copy2(fetch(BASE + name, cache / name, expected), temporary / name)
    notice = (temporary / "main.c").read_text().split("*/", 2)[1] + "*/\n"
    if "Redistribution and use in source and binary forms" not in notice:
        raise ValueError("BSD Adventure port notice changed")
    save = temporary / "save.c"
    original = save.read_text()
    if original.count("#include <endian.h>") != 1:
        raise ValueError("BSD Adventure portability patch no longer applies")
    save.write_text(original.replace("#include <endian.h>", "/* unused NetBSD endian header */"))
    wizard = temporary / "wizard.c"
    original = wizard.read_text()
    if original.count("latency = 45;") != 1:
        raise ValueError("BSD Adventure save patch no longer applies")
    original = original.replace("latency = 45;", "latency = 0;")
    begin = original.index("void\nciao(void)\n{")
    end = original.index("\n\nint\nran(", begin)
    wizard.write_text(original[:begin] + FIXED_SAVE + original[end:])
    (temporary / "compat.h").write_text(COMPAT)
    common = ["/usr/bin/clang", "-std=c99", "-O2", "-arch", "arm64", "-mmacosx-version-min=13.0", "-include", "compat.h"]
    subprocess.run([*common, "-o", "mkdata", "setup.c"], cwd=temporary, check=True, shell=False)
    with (temporary / "data.c").open("wb") as output:
        subprocess.run([str(temporary / "mkdata"), str(temporary / "glorkz")], cwd=temporary,
                       stdout=output, check=True, shell=False)
    target = resources / "adventure"
    target.mkdir(parents=True, exist_ok=True)
    executable = target / "adventure-350"
    subprocess.run([*common, "-fstack-protector-strong", "-o", str(executable),
                    "main.c", "init.c", "done.c", "save.c", "subr.c", "vocab.c",
                    "wizard.c", "io.c", "data.c", "crc.c"], cwd=temporary, check=True, shell=False)
    shutil.copy2(temporary / "glorkz", target / "glorkz-350")
    (target / "COPYING-350").write_text(notice)
    return {
        "name": "BSD Games Adventure, 1977 350-point edition",
        "executable": executable.name,
        "sha256": sha256(executable),
        "game_data": "glorkz-350",
        "game_data_sha256": sha256(target / "glorkz-350"),
        "license": "BSD-3-Clause port notice; game data distributed with the port",
        "source_commit": COMMIT,
        "source_base_url": BASE,
        "source_sha256": SOURCES,
        "port_patches": ["remove unused endian.h include", "macOS NetBSD macro compatibility",
                         "fixed private save path", "permit immediate local restore"],
    }

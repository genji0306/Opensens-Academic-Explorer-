"""Native lab canvas captures from a read-only virtual origin, with audited patches.

Patches are applied to HTTP responses in memory, never to the archived files.
Any source drift fails closed. Browser integration requires the Opus capture run.
"""

import io
import json
import math
import mimetypes
import os
from pathlib import Path
import shlex
import signal
from urllib.parse import unquote, urlsplit

from PIL import Image

from mve.observer import snapshots as s

ORIGIN = "https://mve.invalid"
# Fixed native drawing changes: one spectral sample, matched Ulam palette, and
# exports of exactly the numeric data used by the selected native canvas.
PATCHES = {
    "research.js": [
        ("spectrum=null,seed=2026;", "spectrum=null,seed=20260926;"),
        (
            "const gaps=zetaGaps(+$('spectralCount').value),zg=histogram(gaps)",
            "const gaps=window.__mveControl?spectrum.gaps.slice(0,89):zetaGaps(+$('spectralCount').value),zg=histogram(gaps)",
        ),
        ("Math.max(1.1,...zg,...gg)*1.1", "2"),
        (
            "path(p,gg.flatMap((v,i)=>[[i*.2,v],[(i+1)*.2,v]]),VIOLET,2);path(p,Array.from({length:151},(_,i)=>[i/50,Math.exp(-i/50)]),AMBER,1.8,[5,4]);",
            "window.__mveData={values:Array.from(gaps),seed,source:window.__mveControl?'GUE first 89 gaps':'zeros 11-100'};",
        ),
    ],
    "polar.js": [
        ("synthetic: pack(PINK)", "synthetic: pack(MINT)"),
        (
            "if (set.synthetic) syntheticStamp(c, r.width);",
            "window.__mveData={values:Array.from(set.n),seed:S.seed,source:S.source,N:S.N};",
        ),
    ],
    "field-phase3-overlay.js": [
        (
            "bars(c, L, s.pair, 0.1, (data.set === 'poisson' ? AMBER : data.set === 'zeta' ? WHITE : VIOLET) + '66');",
            "bars(c, L, s.pair, 0.1, WHITE + '66');",
        ),
        (
            "bars(c, Rt, s.hist, 0.2, (data.set === 'poisson' ? AMBER : data.set === 'zeta' ? WHITE : VIOLET) + '66');",
            "bars(c, Rt, s.hist, 0.2, WHITE + '66');",
        ),
    ],
    "field-lab.js": [
        ("boxMode: false, paused: false,", "boxMode: false, paused: true,")
    ],
    "field-phase3.js": [
        (
            "const base = offLine ? statistics(levelSet('zeta', {list})) : null;",
            "window.__mveData={values:segments,seed:DYSON_DEFAULTS.seed,source:params.set,ordinates:params.set==='zeta'?list:null};\n  const base = offLine ? statistics(levelSet('zeta', {list})) : null;",
        ),
    ],
    "prime-sphere.js": [
        (
            "const d = data, {sel, summary} = d, synthetic = sel.synthetic;",
            'const d = data, {sel, summary} = d, synthetic = sel.synthetic; window.__mveData={values:Array.from(sel.n),seed:sel.seed,source:sel.synthetic?"cramer":"primes",options:o};',
        ),
    ],
}
APPEND = {
    "research.js": "\nwindow.__mveSpectralRedraw=()=>drawSpectral();\n",
    "polar.js": "\nwindow.__mvePolarRedraw=()=>drawSpiral();\n",
    "field-lab.js": "\nwindow.__mveFieldRedraw=()=>{P.paused=true;render();};\n",
    "geometry.js": "\nwindow.__mveRedraw=()=>{state.playing=false;render();};\n",
}
INIT_SCRIPT = """(() => {
  window.__mveBlind=false;
  const p=CanvasRenderingContext2D.prototype;
  for (const key of ['fillText','strokeText']) {
    const original=p[key];
    p[key]=function(...args){if(!window.__mveBlind)return original.apply(this,args);};
  }
  // Native data RNGs are explicitly seeded too. Avoid wall-clock randomness.
  let n=20260928;
  Math.random=()=>{n=(Math.imul(1664525,n)+1013904223)>>>0;return n/4294967296;};
})()"""
DATA_JS = "() => window.__mveData"
TEXT_JS = """() => [...new Set([document.title,...document.body.innerText.split('\\n')].map(x=>x.trim()).filter(Boolean))]"""
STATE_JS = """() => ({controls:Object.fromEntries([...document.querySelectorAll('input,select')].filter(x=>x.id).map(x=>[x.id,x.type==='checkbox'?x.checked:x.value])),camera:document.getElementById('geometryCameraPosition')?.value||null})"""
BLIND_JS = """() => {window.__mveBlind=true;
  document.querySelectorAll('#mathboxScene .scene-label').forEach(x=>x.style.visibility='hidden');
  const f={'#field':'__mveFieldRedraw','#spectral':'__mveSpectralRedraw','#polar':'__mvePolarRedraw','#primesphere':'__mveRedraw'};window[f[location.hash]]();
}"""
WITHHELD = [
    "GUE",
    "Poisson",
    "zeta",
    "zeros",
    "prime",
    "primes",
    "Cramér",
    "Cramer",
    "synthetic",
    "Ulam",
    "Dyson",
    "Viviani",
    "Montgomery",
    "RH",
    "density",
]


def transform(filename, text):
    for old, new in PATCHES.get(filename, []):
        if text.count(old) != 1:
            raise ValueError(f"pinned source drift: {filename}")
        text = text.replace(old, new)
    return text + APPEND.get(filename, "")


def route_handler(dist, *, prospective=False):
    def handle(route, request):
        url = urlsplit(request.url)
        if (
            url.scheme != "https"
            or url.netloc != "mve.invalid"
            or request.method != "GET"
        ):
            route.abort()
            return
        try:
            path = s.inside(dist, unquote(url.path).lstrip("/") or "index.html")
            data = path.read_bytes()
        except (ValueError, OSError):
            route.abort()
            return
        if path.suffix == ".js":
            data = transform(path.name, data.decode())
            if prospective:
                data = block_transform(path.name, data)
            data = data.encode()
        route.fulfill(
            status=200,
            body=data,
            content_type=mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            headers={"Cache-Control": "no-store"},
        )

    return handle


def configure(page, job):
    module, null = job["module"], job["control"]["kind"] == "null_twin"
    if module == "spectral":
        page.select_option("#spectralCount", "100")
        page.select_option("#matrixSize", "64")
        page.evaluate("() => window.__mveSpectralRedraw()")
        page.evaluate("""() => {const card=document.querySelector('#spectralPlot').closest('article');
          card.querySelector('h3').textContent='Single-source spacing density';
          card.querySelector('.inline-legend').textContent=window.__mveControl?'Sample: seeded GUE':'Sample: zeta gaps';
        }""")
    elif module == "field-dyson":
        page.click('[data-field-preset="dyson"]')
        page.select_option("#fieldDysonSet", "gue" if null else "zeta")
        page.uncheck("#fieldControl")
        page.uncheck("#fieldDysonAnimate")
        page.wait_for_function(
            "source => window.__mveData?.source===source", arg="gue" if null else "zeta"
        )
        page.evaluate("() => window.__mveFieldRedraw()")
    elif module == "polar-ulam":
        page.select_option("#polarN", "30000")
        page.uncheck("#ulamOverlay")
        page.click('[data-spiral-source="' + ("cramer" if null else "primes") + '"]')
    else:
        page.select_option("#psView", "viviani")
        page.select_option("#psSet", "primes")
        page.locator("#psSynthetic").set_checked(null)
        page.select_option("#psColour", "class")
        page.evaluate("() => window.__mveRedraw()")
        page.wait_for_function(
            "() => document.getElementById('renderError').hidden && document.querySelector('#mathboxScene canvas')"
        )
    page.wait_for_function("() => window.__mveData?.values?.length>0")
    # Two animation frames flush native layout/queued plots without time-driven simulation.
    page.evaluate(
        "() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
    )


def masks_for(module, w, h):
    # Ulam paints a header background and a control stamp inside its canvas.
    # Same fixed regions are blanked for both arms, regardless of text length.
    if module == "polar-ulam":
        return [(0, 0, w, 50), (0, h - 30, w, h)]
    if module == "spectral":
        return [(0, 0, w, 26), (0, h - 44, w, h), (0, 0, 60, h), (w - 20, 0, w, h)]
    if module == "field-dyson":
        boxes = (
            [(0, 0, w // 2, h), (w // 2, 0, w, h)]
            if w >= 520
            else [(0, 0, w, h // 2), (0, h // 2, w, h)]
        )
        return [
            band
            for left, t, r, b in boxes
            for band in [
                (left, t, r, t + 28),
                (left, b - 40, r, b),
                (left, t, left + 45, b),
            ]
        ]
    # This canvas is a source-audited point cloud; DOM pole labels are hidden.
    return []


def assert_nonblank(data):
    with Image.open(io.BytesIO(data)) as im:
        if len(im.convert("RGB").getcolors(maxcolors=16) or range(17)) < 3:
            raise ValueError("blank/failed canvas capture")


def capture_one(context, root, job, versions, ocr):
    folder = s.inside(root, job["snapshot_id"])
    folder.mkdir()
    page = context.new_page()
    try:
        page.add_init_script(INIT_SCRIPT)
        page.add_init_script(
            "window.__mveControl=" + json.dumps(job["control"]["kind"] == "null_twin")
        )
        module = job["module"]
        url = {
            "spectral": "index.html#spectral",
            "field-dyson": "index.html?preset=dyson#field",
            "polar-ulam": "index.html?spiral=ulam#polar",
            "space-08": "geometry.html#primesphere",
        }[module]
        page.goto(ORIGIN + "/" + url, wait_until="load")
        configure(page, job)
        page.evaluate("() => window.scrollTo(0,0)")
        page.evaluate("() => new Promise(r=>requestAnimationFrame(r))")
        data = page.evaluate(DATA_JS)
        null = job["control"]["kind"] == "null_twin"
        expected = {
            "spectral": "GUE first 89 gaps" if null else "zeros 11-100",
            "field-dyson": "gue" if null else "zeta",
            "polar-ulam": "cramer" if null else "primes",
            "space-08": "cramer" if null else "primes",
        }[module]
        if data.get("source") != expected:
            raise ValueError("native source differs from assigned arm")
        if data["seed"] != job["params"]["seed"]:
            raise ValueError("native seed differs from manifest")
        (folder / "data.json").write_text(
            json.dumps(data, sort_keys=True, allow_nan=False, separators=(",", ":"))
            + "\n"
        )
        state = page.evaluate(STATE_JS)
        withheld = page.evaluate(TEXT_JS) + WITHHELD
        canvas = page.locator(s.MODULES[module]["selector"])
        box = canvas.bounding_box()
        if box is None:
            raise ValueError("canvas absent")
        crop = (
            math.floor(box["x"]),
            math.floor(box["y"]),
            math.ceil(box["x"] + box["width"]),
            math.ceil(box["y"] + box["height"]),
        )
        s.disk_guard(
            Path(__file__).resolve().parents[2] / "mve/generated", 10 * 1024**2
        )
        full = folder / "full.png"
        full.write_bytes(page.screenshot(full_page=True, animations="disabled"))
        page.evaluate(BLIND_JS)
        page.evaluate(
            "() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
        )
        raw = page.screenshot(full_page=True, animations="disabled")
        masks = masks_for(module, crop[2] - crop[0], crop[3] - crop[1])
        clean = s.blind_png(raw, crop, masks)
        # Actual browser capture rejects blanks before this function in run_browser;
        # keeping this here ensures fixtures exercise the same rejection boundary.
        assert_nonblank(clean)
        s.assert_regions_clean(clean, masks)
        blind = folder / "blind.png"
        blind.write_bytes(clean)
        leakage = s.leakage_report(blind, withheld, executable=ocr)
        entry = s.make_entry(
            root,
            job,
            full,
            blind,
            folder / "data.json",
            versions,
            crop,
            masks,
            leakage,
            withheld,
        )
        entry["native_state"] = state
        entry["native_state_sha256"] = s.digest(state)
        if module == "spectral":
            entry["atlas_snapshot_id"] = "spectral-gaps-against-gue"
        return entry
    finally:
        page.close()


def chrome_launcher(private, name, chrome):
    """Playwright's POSIX launcher creates a session/group before exec.

    Record its PID before Chrome starts so the parent can kill the whole group
    even if Chrome exits first or Playwright's close hangs on a lingering updater.
    """
    launcher = private / f"{name}-chrome.sh"
    pidfile = private / f"{name}-chrome.pgid"
    launcher.write_text(
        "#!/bin/sh\nset -eu\n"
        f"echo $$ > {shlex.quote(str(pidfile))}\n"
        f'exec {shlex.quote(chrome)} "$@"\n'
    )
    launcher.chmod(0o700)
    return launcher


def kill_browser_groups(private):
    for pidfile in private.glob("*-chrome.pgid"):
        pgid = int(pidfile.read_text().strip())
        if pgid <= 1 or pgid == os.getpgrp():
            raise ValueError("invalid Chrome process group")
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_browser(dist, out, chrome, ocr, private, *, jobs=None, capture=None):
    from importlib.metadata import version
    from playwright.sync_api import sync_playwright

    if jobs is None:
        s.disk_guard(
            Path(__file__).resolve().parents[2] / "mve/generated", 120 * 1024**2
        )
    # The parent supplies one short, private runtime per invocation. Each repeat
    # gets its own profile. Playwright emits --user-data-dir from the first arg.
    profile = private / out.name
    profile.mkdir()
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profile),
            executable_path=str(chrome_launcher(private, out.name, chrome)),
            headless=True,
            # Safe only under the parent's OS sandbox: internet and writes
            # outside the explicit output/runtime allowlist remain denied.
            chromium_sandbox=False,
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=1,
            locale="en-US",
            timezone_id="UTC",
            service_workers="block",
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(private / "h"),
                "TMPDIR": str(private / "t"),
            },
            args=[
                "--headless=new",
                "--no-sandbox",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--ignore-gpu-blocklist",
                "--disable-breakpad",
                "--disable-crash-reporter",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
            ],
        )
        try:
            context.route("**/*", route_handler(dist, prospective=jobs is not None))
            versions = {
                "chrome": context.browser.version,
                "playwright": version("playwright"),
                "Pillow": version("Pillow"),
                "adapter": "WO-1-v1",
                "snapshot_render_sha256": s.sha256(Path(__file__)),
                "viewport": [1440, 1100],
                "device_scale_factor": 1,
                "gpu": "SwiftShader",
                "locale": "en-US",
                "timezone": "UTC",
            }
            if jobs is not None:
                return [capture(context, out, j, versions, ocr) for j in jobs]
            entries = [
                capture_one(context, out, j, versions, ocr) for j in s.capture_jobs()
            ]
            manifest = {"schema": s.SCHEMA, "snapshots": entries}
            s.validate_manifest(manifest, out)
            (out / "manifest.json").write_text(
                json.dumps(manifest, sort_keys=True, indent=2) + "\n"
            )
            return manifest
        finally:
            context.close()


# Applied AFTER the WO-1 patches, to exact pinned response text only. No archive
# file is changed. Export is taken from the variables consumed by native drawing.
BLOCK_PATCHES = {
    "research.js": [
        (
            "const gaps=window.__mveControl?spectrum.gaps.slice(0,89):zetaGaps(+$('spectralCount').value),zg=histogram(gaps)",
            "const gaps=window.__mveBlockModule==='spectral'?window.__mveBlock.values:zetaGaps(+$('spectralCount').value),zg=histogram(gaps)",
        ),
        (
            "window.__mveData={values:Array.from(gaps),seed,source:window.__mveControl?'GUE first 89 gaps':'zeros 11-100'};",
            "if(window.__mveBlockModule==='spectral')window.__mveData={...window.__mveBlock,values:Array.from(gaps)};",
        ),
    ],
    "field-phase3.js": [
        (
            "segments = levelSet(params.set, {list, control: offLine ? ctrl : null}), stats = statistics(segments);",
            "segments = window.__mveBlockModule==='field-dyson'?window.__mveBlock.values:levelSet(params.set, {list, control: offLine ? ctrl : null}), stats = statistics(segments);",
        ),
        (
            "window.__mveData={values:segments,seed:DYSON_DEFAULTS.seed,source:params.set,ordinates:params.set==='zeta'?list:null};",
            "if(window.__mveBlockModule==='field-dyson')window.__mveData={...window.__mveBlock,values:segments};",
        ),
    ],
    "polar.js": [
        (
            "const set = synthetic() ? {n: sample().n, member: sample().member, synthetic: true} : {n: tables().primes, member: tables().isPrime, synthetic: false};",
            "const injected=window.__mveBlockModule==='polar-ulam'; if(injected){S.N=window.__mveBlock.extent;fit(r.width,r.height);} const ns=injected?window.__mveBlock.values:tables().primes; const member=new Uint8Array(S.N+1); ns.forEach(n=>member[n]=1); const set={n:ns,member,synthetic:false};",
        ),
        (
            "window.__mveData={values:Array.from(set.n),seed:S.seed,source:S.source,N:S.N};",
            "if(window.__mveBlockModule==='polar-ulam')window.__mveData={...window.__mveBlock,values:Array.from(set.n)};",
        ),
    ],
    "prime-sphere.js": [
        (
            "const sel = selectIntegers(o.N, o.set, {q: o.q, a: o.a, synthetic: o.synthetic});",
            "o.N=window.__mveBlock.extent; const sel={n:window.__mveBlock.values,N:o.N,set:'primes',synthetic:false,seed:window.__mveBlock.seed,total:window.__mveBlock.values.length,capped:false};",
        ),
        (
            'window.__mveData={values:Array.from(sel.n),seed:sel.seed,source:sel.synthetic?"cramer":"primes",options:o};',
            "if(window.__mveBlockModule==='space-08')window.__mveData={...window.__mveBlock,values:Array.from(sel.n)};",
        ),
    ],
}


def block_transform(filename, text):
    for old, new in BLOCK_PATCHES.get(filename, []):
        if text.count(old) != 1:
            raise ValueError("prospective pinned source drift")
        text = text.replace(old, new)
    return text


def capture_block(context, root, job, versions, ocr):
    """Native capture; return full pages only in RAM for the WO-1 repeat check."""
    from mve.observer import snapshot_inventory as inv
    import hashlib

    block = job["block"]
    page = context.new_page()
    try:
        viewport = block["camera"]["views"][job["view"]]["viewport"]
        page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        page.add_init_script(INIT_SCRIPT)
        page.add_init_script(
            "window.__mveControl=false;window.__mveBlockModule="
            + json.dumps(block["module"])
            + ";window.__mveBlock="
            + job["raw"].decode()
            + ";"
        )
        module = block["module"]
        url = {
            "spectral": "index.html#spectral",
            "field-dyson": "index.html?preset=dyson#field",
            "polar-ulam": "index.html?spiral=ulam#polar",
            "space-08": "geometry.html#primesphere",
        }[module]
        page.goto(ORIGIN + "/" + url, wait_until="load")
        # GUE selector keeps the Dyson field's own display on injected levels,
        # rather than its unrelated default zeta list. Side histogram is selected.
        if module == "field-dyson":
            page.click('[data-field-preset="dyson"]')
            page.select_option("#fieldDysonSet", "gue")
            page.uncheck("#fieldControl")
            page.uncheck("#fieldDysonAnimate")
            page.evaluate("() => window.__mveFieldRedraw()")
        else:
            configure(page, {"module": module, "control": {"kind": "none"}})
        page.wait_for_function("() => window.__mveData?.values?.length>0")
        exported = inv.encoded(page.evaluate(DATA_JS))
        if (
            hashlib.sha256(exported).hexdigest() != block["data_sha256"]
            or exported != job["raw"]
        ):
            raise ValueError("drawn numeric export differs from frozen block")
        page.evaluate("() => window.scrollTo(0,0)")
        page.evaluate(
            "() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
        )
        box = page.locator(block["crop"]["selector"]).bounding_box()
        if box is None:
            raise ValueError("canvas absent")
        crop = [
            math.floor(box["x"]),
            math.floor(box["y"]),
            math.ceil(box["x"] + box["width"]),
            math.ceil(box["y"] + box["height"]),
        ]
        full = page.screenshot(full_page=True, animations="disabled")
        state = page.evaluate(STATE_JS)
        page.evaluate(BLIND_JS)
        page.evaluate(
            "() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
        )
        if inv.encoded(page.evaluate(DATA_JS)) != exported:
            raise ValueError("blind redraw changed data")
        raw = page.screenshot(full_page=True, animations="disabled")
        masks = masks_for(module, crop[2] - crop[0], crop[3] - crop[1])
        clean = s.blind_png(raw, crop, masks)
        s.assert_regions_clean(clean, masks)
        with Image.open(io.BytesIO(clean)) as im:
            output = io.BytesIO()
            im.convert("RGB").resize(
                tuple(block["crop"]["resize"]), Image.Resampling.LANCZOS
            ).save(output, format="PNG")
            clean = output.getvalue()
        assert_nonblank(clean)
        return dict(
            full=full,
            blind=clean,
            data=exported,
            crop=crop,
            masks=masks,
            state=state,
            versions=versions,
        )
    finally:
        page.close()

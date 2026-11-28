# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.55.0", "pexpect==4.9.0", "imageio-ffmpeg>=0.6,<1"]
# ///
"""Record scripted conversations in the real Pi terminal and process them locally."""

import argparse
import asyncio
import codecs
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MOVIES = Path.home() / "Movies" / "edsl-demos"
XTERM = ROOT / "node_modules" / "@xterm" / "xterm"


def ffmpeg(*args):
    from imageio_ffmpeg import get_ffmpeg_exe

    subprocess.run(
        [get_ffmpeg_exe(), "-nostdin", "-v", "error", *map(str, args)], check=True
    )


def make_gif(source, target, args):
    # Never upscale. One palette for the entire clip keeps terminal colors stable.
    filters = (
        f"fps={args.fps},scale='min(iw,{args.width})':-1:flags=lanczos,"
        f"split[a][b];[a]palettegen=max_colors={args.colors}:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    input_flags = ["-ignore_loop", "1"] if source.suffix.lower() == ".gif" else []
    ffmpeg(*input_flags, "-i", source, "-vf", filters, "-loop", "0", target)


async def terminal_session(page, prompts, workdir, scratch, timeout):
    import pexpect

    events = scratch / "events"
    events.touch()
    await page.set_content(
        '<style>html,body{margin:0;background:#151719}#term{padding:12px 16px}</style><div id="term"></div>'
    )
    await page.add_style_tag(path=XTERM / "css/xterm.css")
    await page.add_script_tag(path=XTERM / "lib/xterm.js")
    await page.evaluate(
        """() => {
        window.term = new Terminal({cols:94,rows:32,fontSize:18,fontFamily:'Menlo,monospace',
            cursorBlink:false,theme:{background:'#151719',foreground:'#eeefea'}});
        term.open(document.getElementById('term'));
    }"""
    )
    pi_env = dict(os.environ)
    pi_env["PATH"] = pi_env.pop("PI_SCREENCAST_CALLER_PATH", pi_env["PATH"])
    caller_venv = pi_env.pop("PI_SCREENCAST_CALLER_VENV", pi_env.get("VIRTUAL_ENV"))
    if caller_venv:
        pi_env["VIRTUAL_ENV"] = caller_venv
    else:
        pi_env.pop("VIRTUAL_ENV", None)
    pi_env.update(
        TERM="xterm-256color", COLORTERM="truecolor", PI_SCREENCAST_EVENTS=str(events)
    )
    pi = shutil.which("pi", path=pi_env["PATH"])
    if not pi:
        raise ValueError("The pi executable must be on PATH.")
    child = pexpect.spawn(
        pi,
        ["--no-session", "-e", str(ROOT / "progress.ts")],
        cwd=str(workdir),
        dimensions=(32, 94),
        echo=False,
        env=pi_env,
    )
    try:
        await page.expose_function(
            "reply", lambda s: os.write(child.child_fd, s.encode())
        )
        await page.evaluate("() => term.onData(s => window.reply(s))")
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        os.set_blocking(child.child_fd, False)

        async def pump():
            while child.isalive():
                try:
                    chunk = os.read(child.child_fd, 65536)
                except BlockingIOError:
                    await asyncio.sleep(0.02)
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                await page.evaluate(
                    "s => new Promise(done => term.write(s, done))",
                    decoder.decode(chunk),
                )

        output = asyncio.create_task(pump())

        async def wait_for(event, count):
            deadline = asyncio.get_running_loop().time() + timeout
            while asyncio.get_running_loop().time() < deadline:
                if output.done():
                    await output
                    raise RuntimeError("Pi exited before completing the recording.")
                lines = events.read_text().splitlines()
                if "failed" in lines:
                    raise RuntimeError(
                        "Pi reported a failed or aborted turn. Check the provider in Pi."
                    )
                if lines.count(event) >= count:
                    return
                if event == "ready":
                    screen = await page.evaluate(
                        """() => Array.from({length:term.rows}, (_,i) =>
                        term.buffer.active.getLine(i)?.translateToString(true)).join(' ')"""
                    )
                    if "Trust project folder?" in screen:
                        raise RuntimeError(
                            f"Open Pi in {workdir} and answer the project trust question first."
                        )
                await asyncio.sleep(0.15)
            raise RuntimeError(
                f"Timed out waiting for Pi ({event}). Check login or interactive prompts in the project."
            )

        try:
            await wait_for("ready", 1)
            await asyncio.sleep(0.8)
            for number, prompt in enumerate(prompts, 1):
                print(
                    f"Recording prompt {number} of {len(prompts)}",
                    file=sys.stderr,
                    flush=True,
                )
                for ch in prompt:
                    os.write(child.child_fd, ch.encode())
                    await asyncio.sleep(0.028)
                await asyncio.sleep(0.5)
                os.write(child.child_fd, b"\r")
                await wait_for("done", number)
                await asyncio.sleep(1.5)
            await asyncio.sleep(4)
        finally:
            output.cancel()
            await asyncio.gather(output, return_exceptions=True)
    finally:
        child.close(force=True)


async def record(prompts, workdir, scratch, timeout):
    from playwright.async_api import async_playwright

    if not (XTERM / "lib/xterm.js").is_file():
        raise ValueError(
            f"Run npm ci --prefix {ROOT} to install the terminal renderer."
        )
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            size = {"width": 1100, "height": 722}
            ctx = await browser.new_context(
                viewport=size, record_video_size=size, record_video_dir=scratch
            )
            page = await ctx.new_page()
            try:
                await terminal_session(page, prompts, workdir, scratch, timeout)
            finally:
                await ctx.close()
            return await page.video.path()
        finally:
            await browser.close()


def positive(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def main():
    parser = argparse.ArgumentParser(prog="pi-video", description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    rec = commands.add_parser(
        "record", help="run one Pi turn per nonblank line and save an MP4"
    )
    rec.add_argument("source", type=Path, metavar="PROMPTS.txt")
    rec.add_argument(
        "--workdir",
        type=Path,
        help="existing Pi project (default: temporary empty folder)",
    )
    rec.add_argument(
        "--timeout", type=positive, default=240, help="seconds per turn (default 240)"
    )
    gif = commands.add_parser("gif", help="convert a video to a looping GIF")
    compress = commands.add_parser(
        "compress", help="make a smaller copy of an animated GIF"
    )
    for cmd, fps, width, colors in [(gif, 10, 1100, 128), (compress, 6, 800, 64)]:
        cmd.add_argument("source", type=Path)
        cmd.add_argument(
            "--fps",
            type=positive,
            default=fps,
            help=f"frames per second (default {fps})",
        )
        cmd.add_argument(
            "--width",
            type=positive,
            default=width,
            help=f"maximum pixel width (default {width})",
        )
        cmd.add_argument(
            "--colors",
            type=int,
            default=colors,
            help=f"palette size, 4–256 (default {colors})",
        )
    for cmd in (rec, gif, compress):
        cmd.add_argument(
            "-o",
            "--output",
            type=Path,
            help="output file (default: ~/Movies/edsl-demos)",
        )
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    suffix = ".mp4" if args.action == "record" else ".gif"
    stem = source.stem + ("-small" if args.action == "compress" else "")
    dest = (args.output or MOVIES / (stem + suffix)).expanduser().absolute()
    if dest.suffix.lower() != suffix:
        parser.error(f"output must end in {suffix}")
    if dest.exists():
        parser.error(f"{dest} already exists. Choose a new output with -o.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
        scratch = Path(temp)
        target = scratch / ("output" + suffix)
        if args.action == "record":
            prompts = [
                s.strip()
                for s in source.read_text(encoding="utf-8").splitlines()
                if s.strip()
            ]
            if not prompts or any(
                s.startswith(("!", "/")) or not s.isprintable() for s in prompts
            ):
                parser.error(
                    "use one plain-language prompt per line in a nonempty UTF-8 file"
                )
            workdir = (
                args.workdir.resolve(strict=True) if args.workdir else scratch / "study"
            )
            if not args.workdir:
                workdir.mkdir()
            if not workdir.is_dir():
                parser.error("--workdir must be a directory")
            raw = asyncio.run(record(prompts, workdir, scratch, args.timeout))
            ffmpeg(
                "-i",
                raw,
                "-an",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                target,
            )
        else:
            if not 4 <= args.colors <= 256:
                parser.error("--colors must be between 4 and 256")
            if args.action == "compress" and source.suffix.lower() != ".gif":
                parser.error("compress expects a GIF")
            make_gif(source, target, args)
            if (
                args.action == "compress"
                and target.stat().st_size >= source.stat().st_size
            ):
                shutil.copyfile(source, target)
                print(
                    "The original GIF was already smaller; kept its encoding.",
                    file=sys.stderr,
                )
        os.link(target, dest)
    print(f"{dest} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))

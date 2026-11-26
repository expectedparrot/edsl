# Record the EDSL demos

The three GIFs in [gifs/](gifs/) follow the same coffee survey from design to data collection. Use these scripts from the `videos/` directory to record another take or edit the [plain-language prompts](prompts/) to try a different study.

## Set up

Install [Pi for EDSL](../harnesses/README.md), uv, and npm on macOS or Linux. Start Pi once in the study directory to complete any login or project trust prompts. Use an active Python environment that contains EDSL.

```sh
npm ci
uvx --from playwright==1.55.0 playwright install chromium
mkdir -p "$HOME/Movies/edsl-demos"
study=$(mktemp -d "$HOME/Movies/edsl-demos/coffee-study.XXXXXX")
cp study-guide.md "$study/AGENTS.md"
```

The recorder opens Pi in a real terminal, types one prompt per nonblank line, and waits for Pi to finish each turn. The `--workdir` option keeps the survey and results across sessions. Recordings default to `~/Movies/edsl-demos`. Use `-o` to choose a new filename for another take.

## Build and edit the survey

```sh
./pi-video record prompts/build.txt --workdir "$study"
./pi-video gif ~/Movies/edsl-demos/build.mp4
./pi-video compress ~/Movies/edsl-demos/build.gif
```

The third command writes `build-small.gif`. Use `--width`, `--fps`, and `--colors` on either GIF command to tune file size and readability.

## Run the simulated interviews

Use an Expected Parrot API key and sufficient credits for hosted inference. Pi runs the saved questionnaire across three personas and three models. The GIF in this repository uses GPT-6.2 Astra, Claude Opus 5.5, and Gemini 3.1 Pro Preview. [Model access and API keys](../docs/en/latest/api_keys.mdx)

```sh
./pi-video record prompts/personas.txt --workdir "$study" --timeout 900
./pi-video gif ~/Movies/edsl-demos/personas.mp4
```

## Record a browser response and retrieve it

First record Pi creating the respondent link. The browser script opens that link and submits **one live test response**. It answers Yes, chooses Espresso, and types a morning drink. If your survey has different brew options, pass the exact label with `--brew`. Then record Pi retrieving the completed responses.

```sh
out="$HOME/Movies/edsl-demos"
./pi-video record prompts/share.txt --workdir "$study"
url=$(python3 -c 'import json, sys; d=json.load(open(sys.argv[1])); assert d["status"] == "ok"; print(d["data"]["respondent_url"])' "$study/deployment.json")
uv run --script record_coffee_response.py "$url" "$out/browser.webm"
./pi-video record prompts/results.txt --workdir "$study"
```

To join the terminal and browser clips, use FFmpeg and then convert the resulting video to a GIF. For a shorter README cut, trim idle time in the MP4 and hold the frames that show routing, the respondent URL, or the final results.

```sh
ffmpeg -n -i "$out/share.mp4" -i "$out/browser.webm" -i "$out/results.mp4" \
  -filter_complex '[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]' -map '[v]' \
  -r 24 -pix_fmt yuv420p "$out/human-responses.mp4"
./pi-video gif "$out/human-responses.mp4"
```

To publish a new take, copy the selected GIF into `gifs/` and check the matching section of the [repository README](../README.md).

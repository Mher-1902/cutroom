# Cutroom desktop app

Open **Cutroom.app** on your Desktop. It starts the existing local studio and opens it in a native Mac window, with upload dialogs, video playback and file-save dialogs. No Terminal command is needed for normal use. Closing or quitting the desktop window leaves the background studio and its jobs running. The app menu also offers Open in Browser.

This desktop window uses the original project and its existing models/data; keep that project folder in place. It does not fix or bypass the pending automatic editing acceptance checks described in `VERIFICATION.md`.

To rebuild from a new project location, double-click **Build Desktop.command** (requires Apple's Command Line Tools). It creates `Cutroom.app` beside the project. Existing apps are not overwritten; choose another output with `./"Build Desktop.command" --output /path/to/Cutroom.app`. The bundle contains a native Swift/AppKit/WebKit executable, a local icon and the path to the studio. Model weights remain in the project folder.

# Use Cutroom without this chat

## On this Mac

Double-click **Launch.command** in Finder. It starts the studio in the background and opens **http://127.0.0.1:8765**. Bookmark that URL in Chrome, Safari, or your preferred browser. Closing the browser, terminal, or agent chat does not stop this background instance.

Alternatively, open Terminal in the project folder and run:

```sh
./cutroom.command start
```

For overnight processing while plugged into power:

```sh
./cutroom.command start --keep-awake
```

The Mac must remain on and awake. `--keep-awake` prevents idle system sleep while this studio process lives; the display can turn off. Closing a laptop lid or manually selecting Sleep can still suspend processing. Stop the studio with `./cutroom.command stop` to release the sleep assertion. [Apple's sleep behavior](https://developer.apple.com/library/archive/qa/qa1340/_index.html)

These commands are safe to repeat; Start reuses a running instance of this installation. `./cutroom.command status` reports its state. `./cutroom.command logs` shows recent log output from `data/studio.log`. After restarting the Mac, start Cutroom again. After interruption, use **Your projects → Resume run**; processing does not automatically resume a potentially large GPU job at login.

For foreground debugging, use `data/venv/bin/python app.py --no-browser`. Keep that terminal open; Control-C stops the foreground process. Avoid launching both ways during an active run. Installation locking and binding before project loading prevent duplicate instances from changing live job state.

## Fresh installation from GitHub

```sh
git clone https://github.com/Mher-1902/cutroom.git
cd cutroom
./Install.command
./Launch.command
```

Homebrew and Apple's Command Line Tools must already be installed. In **Inside the engine**, run **Finish local setup**. Model weights and environments are deliberately excluded from the public repository. Setup downloads them to this installation's `data/` directory. A fresh clone does not inherit existing models or projects; keep using the original installation if you want its current data. Do not copy data while a job is writing it.

## Access and 24/7 operation

For this version, **your Mac is the server**. It is available whenever the studio is running and the Mac is awake. It needs no paid web hosting, and this chat is not involved in normal use. This is availability on your own Mac, not a guarantee of uninterrupted operation while the machine is sleeping or powered off.

GitHub stores and shares the code. GitHub Pages serves static files and cannot run this Python backend, native macOS Vision, FFmpeg jobs, or local model processes. An ordinary static hosting upload would show a disconnected interface. [GitHub Pages limitations](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

For access from another computer, private networking plus an authenticated SSH local-port tunnel is an option. Tailscale has a free personal plan and documents SSH forwarding; it requires account/device setup and is not configured here. Keep the browser endpoint at `http://127.0.0.1:8765` through the tunnel, because the app intentionally validates loopback Host and Origin headers. A direct public tunnel or domain will not work with the current checks. [Tailscale plans](https://tailscale.com/pricing), [SSH forwarding](https://tailscale.com/docs/reference/ssh-over-tailscale)

An internet-hosted multi-user version needs authentication, isolation, persistent storage, a queue, compatible model compute, and a replacement or separate Mac worker for native Vision. Those deployment changes have not been implemented. This version binds only to loopback and should remain a private local service.

## Current test status

The interface, local models, renderer, checkpoint system, and source import are available to test. The user approved the 71.72-second portrait editing preview. Native vLLM Metal model calibration and hardware rendering passed their measured checks. The full autonomous reference-video run remains in progress; no promise of ten qualifying results, virality, rights clearance, or platform payouts is made. See [VERIFICATION.md](VERIFICATION.md).

## When another model server is running

Cutroom waits before loading its model when it detects another vLLM server on the Mac. The project shows **Waiting for your other model server**. You can leave the browser closed: the job continues automatically once that other server closes, or use **Stop & save progress** to cancel the wait. Cutroom never stops another project's model server. The full automatic reference-video acceptance test remains unfinished; see `VERIFICATION.md` for current failures and fixes.

## Authorized browser import denied by macOS

Checking the browser-session box authorizes Cutroom; it does not override macOS privacy controls. Safari and Chrome directory checks on this Mac returned `Operation not permitted`. Chrome's downloader reported that as a missing database, so the importer now checks authorized Chrome directory access before downloading and reports the OS denial accurately.

For browser-session imports, the next permission step is **System Settings → Privacy & Security → Full Disk Access → add/enable Cutroom.app** from the Desktop. This is broad access to protected files, not just a YouTube permission. A local video upload avoids needing browser access. [Apple's explanation of Full Disk Access](https://support.apple.com/en-au/guide/mac-help/mchl211c911f/mac).

Launch the backend through the Cutroom desktop app. After changing the permission, the local backend must be restarted as well as the window; closing the window alone intentionally leaves that backend running. The assistant can stop the local studio, reopen the desktop app and retry the saved project after the user grants permission. macOS permission changes require the user; the app does not grant them automatically. The authorized Chrome retry remains blocked until access is available, and a successful download has not been claimed.

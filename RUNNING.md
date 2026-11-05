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

The interface, local models, renderer, checkpoint system, and source import are available to test. A real 72.1-second manually selected renderer preview passed technical checks. The full autonomous reference-video run remains in progress; no promise of ten qualifying results, virality, rights clearance, or platform payouts is made. See [VERIFICATION.md](VERIFICATION.md).

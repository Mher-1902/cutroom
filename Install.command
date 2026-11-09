#!/bin/zsh
set -eu
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v brew >/dev/null; then
  print 'Homebrew is required. Install it from https://brew.sh, then run this file again.'
  read -k 1 '?Press any key to close.'
  exit 1
fi
print 'Installing free local video and AI tools. No subscriptions or paid APIs are used.'
HOMEBREW_NO_AUTO_UPDATE=1 brew install ffmpeg-full whisper-cpp yt-dlp uv
print 'Tools installed. Open Launch.command, then Local models to download the models.'
read -k 1 '?Press any key to close.'

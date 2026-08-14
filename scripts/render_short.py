#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path


def duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def scene_times(path):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vf", "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [float(value) for value in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def endpoint(path):
    total = duration(path)
    cuts = scene_times(path)
    start = total * 0.38
    latest = max(start, total - 4.0)
    candidates = [cut for cut in cuts if start <= cut <= latest]
    for cut in candidates:
        if sum(cut < other <= cut + 4.0 for other in cuts) >= 2:
            return min(total, cut + 4.0)
    return min(total, total * 0.72 + 4.0)


def esc(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def main():
    if len(sys.argv) != 6:
        raise SystemExit("Usage: render_short.py CLIP3 CLIP2 LABEL3 LABEL2 OUTPUT")
    clip3 = Path(sys.argv[1])
    clip2 = Path(sys.argv[2])
    label3 = sys.argv[3]
    label2 = sys.argv[4]
    output = Path(sys.argv[5])
    end3, end2 = endpoint(clip3), endpoint(clip2)
    font = "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
    l3, l2 = esc(str(label3)), esc(str(label2))
    filters = f"""
    [0:v]trim=0:{end3},setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,
      drawtext=fontfile='{font}':text='#3  {l3}':fontcolor=white:fontsize=58:x=54:y=90:borderw=5:bordercolor=black[v3];
    [0:a]atrim=0:{end3},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo[a3];
    [1:v]trim=0:{end2},setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,
      drawtext=fontfile='{font}':text='#3  {l3}':fontcolor=white:fontsize=42:x=54:y=72:borderw=4:bordercolor=black,
      drawtext=fontfile='{font}':text='#2  {l2}':fontcolor=yellow:fontsize=58:x=54:y=142:borderw=5:bordercolor=black[v2];
    [1:a]atrim=0:{end2},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo[a2];
    [v3][a3][v2][a2]concat=n=2:v=1:a=1[outv][outa]
    """.replace("\n", "")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(clip3), "-i", str(clip2), "-filter_complex", filters,
        "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(output)
    ], check=True)


if __name__ == "__main__":
    main()

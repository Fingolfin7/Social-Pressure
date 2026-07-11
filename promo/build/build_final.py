"""Final assembly: splice the user's phone clips in place of the placeholder.

Reuses already-encoded segments 01-09 and the end card; encodes the phone
segments (9:20 HEVC -> 9:16 with blurred pillarbox), then concats + music.
"""
import os
import subprocess

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SEGS = os.path.join(SCRATCH, "segs")
PHONE = "C:/Users/mushu/Downloads/Claude Vid/Screenrecorder-2026-07-10-14-15-01-472.mp4"
FONT = "C\\:/Windows/Fonts/segoeuib.ttf"
MUSIC = os.path.join(SCRATCH, "music_funkorama.mp3")
OUT = os.path.join(SCRATCH, "social_pressure_promo_final.mp4")


def drawtext(text, start, end, y=1560, size=56):
    safe = text.replace("\\", "").replace("'", "’").replace(":", "\\:")
    return (
        f"drawtext=fontfile='{FONT}':text='{safe}':fontsize={size}:fontcolor=white:"
        f"box=1:boxcolor=0x26221D@0.78:boxborderw=26:line_spacing=10:"
        f"x=(w-text_w)/2:y={y}:enable='between(t,{start},{end})'"
    )


def run(cmd):
    print(">>", os.path.basename(cmd[-1]))
    subprocess.run(cmd, check=True, capture_output=True)


# (name, trim_start, trim_end, speed, [(text, cap_start, cap_end)])
PHONE_SEGMENTS = [
    ("p1_perm", 14.2, 18.8, 1.2,
     [("Allow it once.", 0.3, 3.4)]),
    ("p2_test", 115.8, 119.2, 1.2,
     [("There's even a test button...", 0.1, 2.7)]),
    ("p3_payoff", 124.3, 128.2, 1.15,
     [("...and there it is.", 0.4, 3.1)]),
    ("p4_install", 9.0, 14.2, 1.25,
     [("It installs like a real app, too.", 0.2, 3.9)]),
]

phone_durs = {}
for name, t0, t1, speed, caps in PHONE_SEGMENTS:
    dur = (t1 - t0) / speed
    phone_durs[name] = dur
    caps_f = "".join("," + drawtext(t, a, b) for t, a, b in caps)
    fc = (
        f"[0:v]trim=start={t0}:end={t1},setpts=(PTS-STARTPTS)/{speed},fps=30,split[a][b];"
        f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"gblur=sigma=24,eq=brightness=-0.06[bg];"
        f"[b]scale=-2:1920[fg];"
        f"[bg][fg]overlay=(W-w)/2:0{caps_f},format=yuv420p[v]"
    )
    out = os.path.join(SEGS, f"{name}.mp4")
    run([
        "ffmpeg", "-y", "-v", "error", "-i", PHONE,
        "-filter_complex", fc, "-map", "[v]",
        "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        out,
    ])

# Existing segment durations (from build_video.py definitions).
EXISTING = [
    ("01_hook.mp4", (7.5 - 1.2) / 1.25),
    ("02_form.mp4", 2.0),
    ("03_target.mp4", (12.0 - 8.4) / 1.15),
    ("04_invite.mp4", (17.6 - 13.9) / 1.15),
    ("05_join.mp4", (9.6 - 0.8) / 1.35),
    ("06_log.mp4", (14.6 - 3.0) / 1.4),
    ("07_partner_a.mp4", 2.4),
    ("08_partner_b.mp4", (20.8 - 9.4) / 1.45),
    ("09_push.mp4", (4.9 - 0.8) / 1.1),
]

order = [os.path.join(SEGS, f) for f, _ in EXISTING]
order += [os.path.join(SEGS, f"{n}.mp4") for n, *_ in PHONE_SEGMENTS]
order.append(os.path.join(SEGS, "11_end.mp4"))

total = sum(d for _, d in EXISTING) + sum(phone_durs.values()) + 4.5

concat_list = os.path.join(SEGS, "list_final.txt")
with open(concat_list, "w") as f:
    for path in order:
        f.write(f"file '{path}'\n".replace("\\", "/"))

silent = os.path.join(SEGS, "concat_final.mp4")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
     "-i", concat_list, "-c", "copy", silent])

print(f"total ~{total:.1f}s")
run([
    "ffmpeg", "-y", "-v", "error",
    "-i", silent, "-i", MUSIC,
    "-filter_complex",
    f"[1:a]atrim=0:{total:.2f},volume=0.38,"
    f"afade=t=in:st=0:d=0.6,afade=t=out:st={total - 3:.2f}:d=3[a]",
    "-map", "0:v", "-map", "[a]",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
    "-movflags", "+faststart",
    OUT,
])
print("built", OUT)

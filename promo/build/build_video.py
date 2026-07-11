"""Assemble the promo video: trim/speed clips, burn captions, concat, add music."""
import os
import subprocess

SCRATCH = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(SCRATCH, "clips")
SEGS = os.path.join(SCRATCH, "segs")
os.makedirs(SEGS, exist_ok=True)

FONT = "C\\:/Windows/Fonts/segoeuib.ttf"
OUT = os.path.join(SCRATCH, "social_pressure_promo_draft.mp4")
MUSIC = os.path.join(SCRATCH, "music_funkorama.mp3")


def drawtext(text, start, end, y=1560, size=56):
    safe = text.replace("\\", "").replace("'", "’").replace(":", "\\:")
    return (
        f"drawtext=fontfile='{FONT}':text='{safe}':fontsize={size}:fontcolor=white:"
        f"box=1:boxcolor=0x26221D@0.78:boxborderw=26:line_spacing=10:"
        f"x=(w-text_w)/2:y={y}:enable='between(t,{start},{end})'"
    )


# (name, src, trim_start, trim_end, speed, [(text, cap_start, cap_end), ...], extra)
SEGMENTS = [
    ("01_hook", "hook.webm", 1.2, 7.5, 1.25,
     [("Quitting is easy when nobody's watching.", 0.2, 2.6),
      ("So let someone watch.", 2.7, 4.9)],
     "fade=t=in:st=0:d=0.35"),
    ("02_form", "create.webm", 1.0, 3.0, 1.0,
     [("Pick a goal. Any habit, any pace.", 0.1, 2.0)], None),
    ("03_target", "create.webm", 8.4, 12.0, 1.15,
     [("Set your own weekly target.", 0.1, 3.0)], None),
    ("04_invite", "create.webm", 13.9, 17.6, 1.15,
     [("Send one link to a friend.", 0.1, 3.1)], None),
    ("05_join", "join.webm", 0.8, 9.6, 1.35,
     [("They pick their target...", 0.3, 3.2),
      ("...and you're in it together.", 3.4, 6.4)], None),
    ("06_log", "log.webm", 3.0, 14.6, 1.4,
     [("Did it? One tap.", 1.6, 4.4),
      ("That's the whole job.", 4.6, 8.1)], None),
    ("07_partner_a", "partner.webm", 1.2, 3.6, 1.0,
     [("Your buddy's phone, seconds later...", 0.1, 2.4)], None),
    ("08_partner_b", "partner.webm", 9.4, 20.8, 1.45,
     [("...sees it land in real time.", 0.1, 2.5),
      ("React to their check-ins...", 2.7, 5.2),
      ("...or nudge them when they slack.", 5.4, 7.8)], None),
    ("09_push", "push.webm", 0.8, 4.9, 1.1,
     [("Get a ping when they check in.", 0.3, 3.6)], None),
]

STILLS = [
    ("10_phone", "card_phone.png", 5.0, None),
    ("11_end", "card_end.png", 4.5, "fade=t=in:st=0:d=0.3,fade=t=out:st=4.0:d=0.5"),
]


def run(cmd):
    print(">>", " ".join(cmd)[:160])
    subprocess.run(cmd, check=True, capture_output=True)


seg_files = []
for name, src, t0, t1, speed, caps, extra in SEGMENTS:
    dur = (t1 - t0) / speed
    filters = [
        f"trim=start={t0}:end={t1}",
        f"setpts=(PTS-STARTPTS)/{speed}",
        "fps=30",
    ]
    if extra:
        filters.append(extra)
    for text, cs, ce in caps:
        filters.append(drawtext(text, cs, ce))
    filters.append("format=yuv420p")
    out = os.path.join(SEGS, f"{name}.mp4")
    run([
        "ffmpeg", "-y", "-v", "error",
        "-i", os.path.join(CLIPS, src),
        "-vf", ",".join(filters),
        "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        out,
    ])
    seg_files.append((out, dur))

for name, img, dur, extra in STILLS:
    out = os.path.join(SEGS, f"{name}.mp4")
    vf = "fps=30,format=yuv420p" + (f",{extra}" if extra else "")
    run([
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1", "-t", str(dur), "-i", os.path.join(SCRATCH, img),
        "-vf", vf,
        "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        out,
    ])
    seg_files.append((out, dur))

concat_list = os.path.join(SEGS, "list.txt")
with open(concat_list, "w") as f:
    for path, _ in seg_files:
        f.write(f"file '{path}'\n".replace("\\", "/"))

silent = os.path.join(SEGS, "concat.mp4")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
     "-i", concat_list, "-c", "copy", silent])

total = sum(d for _, d in seg_files)
print(f"total video duration ~{total:.1f}s")

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

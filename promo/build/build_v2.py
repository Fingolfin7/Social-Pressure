"""v2: add the home-screen-launch + Android OS dialog beat and the CTA end card."""
import os
import subprocess

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SEGS = os.path.join(SCRATCH, "segs")
PHONE = "C:/Users/mushu/Downloads/Claude Vid/Screenrecorder-2026-07-10-14-15-01-472.mp4"
FONT = "C\\:/Windows/Fonts/segoeuib.ttf"
MUSIC = os.path.join(SCRATCH, "music_funkorama.mp3")
OUT = os.path.join(SCRATCH, "social_pressure_promo_v2.mp4")


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


# The new phone beat: home icon -> splash -> standalone app -> OS dialog -> pings on.
P5 = ("p5_os", 97.9, 109.5, 1.45, [
    ("Straight from your home screen.", 0.3, 3.6),
    ("One more allow for Android...", 4.0, 6.2),
    ("...and you're set.", 6.5, 7.9),
])

# Re-caption p3 since the test-button beat (p2) is dropped.
P3 = ("p3_payoff_v2", 124.3, 128.2, 1.15, [
    ("Pings land like texts.", 0.4, 3.1),
])

for name, t0, t1, speed, caps in (P5, P3):
    caps_f = "".join("," + drawtext(t, a, b) for t, a, b in caps)
    fc = (
        f"[0:v]trim=start={t0}:end={t1},setpts=(PTS-STARTPTS)/{speed},fps=30,split[a][b];"
        f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"gblur=sigma=24,eq=brightness=-0.06[bg];"
        f"[b]scale=-2:1920[fg];"
        f"[bg][fg]overlay=(W-w)/2:0{caps_f},format=yuv420p[v]"
    )
    run(["ffmpeg", "-y", "-v", "error", "-i", PHONE,
         "-filter_complex", fc, "-map", "[v]",
         "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         os.path.join(SEGS, f"{name}.mp4")])

# New end card segment.
run(["ffmpeg", "-y", "-v", "error",
     "-loop", "1", "-t", "4.5", "-i", os.path.join(SCRATCH, "card_end_v2.png"),
     "-vf", "fps=30,format=yuv420p,fade=t=in:st=0:d=0.3,fade=t=out:st=4.0:d=0.5",
     "-an", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
     os.path.join(SEGS, "12_end_v2.mp4")])

ORDER = [
    ("01_hook.mp4", (7.5 - 1.2) / 1.25),
    ("02_form.mp4", 2.0),
    ("03_target.mp4", (12.0 - 8.4) / 1.15),
    ("04_invite.mp4", (17.6 - 13.9) / 1.15),
    ("05_join.mp4", (9.6 - 0.8) / 1.35),
    ("06_log.mp4", (14.6 - 3.0) / 1.4),
    ("07_partner_a.mp4", 2.4),
    ("08_partner_b.mp4", (20.8 - 9.4) / 1.45),
    ("09_push.mp4", (4.9 - 0.8) / 1.1),
    ("p1_perm.mp4", (18.8 - 14.2) / 1.2),
    ("p3_payoff_v2.mp4", (128.2 - 124.3) / 1.15),
    ("p4_install.mp4", (14.2 - 9.0) / 1.25),
    ("p5_os.mp4", (109.5 - 97.9) / 1.45),
    ("12_end_v2.mp4", 4.5),
]

concat_list = os.path.join(SEGS, "list_v2.txt")
with open(concat_list, "w") as f:
    for fname, _ in ORDER:
        f.write(f"file '{os.path.join(SEGS, fname)}'\n".replace("\\", "/"))

silent = os.path.join(SEGS, "concat_v2.mp4")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
     "-i", concat_list, "-c", "copy", silent])

total = sum(d for _, d in ORDER)
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

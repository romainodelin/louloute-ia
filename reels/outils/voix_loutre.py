"""Variantes de « voix de loutre » : entre Vivienne (naturelle) et Eloise (jeune, pétillante).
Usage : python outils/voix_loutre.py   -> reels/sortie/loutre_*.mp3"""
import asyncio, os, subprocess, edge_tts
try: import imageio_ffmpeg; FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError: FF = "ffmpeg"
TEXTE = ("Une heure par jour sur tes mails ? Bon... j'ai un truc pour toi. "
         "Trois prompts, et t'as fini en dix minutes. Allez, on regarde le premier.")
OUT = os.path.join(os.path.dirname(__file__), "..", "sortie")
VIV, ELO = "fr-FR-VivienneMultilingualNeural", "fr-FR-EloiseNeural"
# nom : (voix, débit, hauteur, effet « personnage » ffmpeg ou None)
VARIANTES = {
    "A_vivienne_pep":       (VIV, "+6%", "+12Hz", None),
    "B_vivienne_jeune":     (VIV, "+8%", "+25Hz", None),
    "C_vivienne_cartoon":   (VIV, "+2%", "+0Hz",  1.10),   # timbre plus « petit animal »
    "D_eloise_posee":       (ELO, "-4%", "-4Hz",  None),
    "E_eloise_naturelle":   (ELO, "+0%", "+0Hz",  None),
    "F_mix_cartoon_doux":   (VIV, "+4%", "+8Hz",  1.06),
}
async def main():
    for nom, (voix, debit, hauteur, effet) in VARIANTES.items():
        brut, fin = os.path.join(OUT, f"_tmp_{nom}.mp3"), os.path.join(OUT, f"loutre_{nom}.mp3")
        await edge_tts.Communicate(TEXTE, voix, rate=debit, pitch=hauteur).save(brut)
        if effet:   # monte le timbre sans changer la vitesse
            subprocess.run([FF, "-y", "-loglevel", "error", "-i", brut, "-af",
                            f"asetrate=24000*{effet},aresample=24000,atempo={1/effet:.4f}", fin], check=True)
            os.remove(brut)
        else:
            os.replace(brut, fin)
        print("OK", nom)
asyncio.run(main())

"""Génère la même phrase avec plusieurs voix Edge pour comparer à l'oreille.
Usage : python outils/comparer_voix.py   -> reels/sortie/voix_*.mp3"""
import asyncio, os, edge_tts
TEXTE = ("Une heure par jour sur tes mails ? Bon... j'ai un truc pour toi. "
         "Trois prompts, et t'as fini en dix minutes. Allez, on regarde le premier.")
VOIX = ["fr-FR-VivienneMultilingualNeural", "fr-FR-RemyMultilingualNeural",
        "fr-FR-DeniseNeural", "fr-FR-EloiseNeural", "fr-FR-HenriNeural", "fr-CA-SylvieNeural"]
OUT = os.path.join(os.path.dirname(__file__), "..", "sortie")
async def main():
    for v in VOIX:
        f = os.path.join(OUT, f"voix_{v}.mp3")
        try: await edge_tts.Communicate(TEXTE, v, rate="+4%", pitch="-2Hz").save(f); print("OK", v)
        except Exception as e: print("échec", v, e)
asyncio.run(main())

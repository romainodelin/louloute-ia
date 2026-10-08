"""Générateur de Reels Louloutre (v2).

Usage :  python make_reel.py scripts/<fichier>.json
Sortie : reels/sortie/<id>.mp4  (1080x1920, 30 i/s)

Script JSON :
  {"id": "...", "voix": "fr-FR-VivienneMultilingualNeural", "vitesse": "+6%",
   "scenes": [
     {"type": "titre",  "voix": "texte lu", "ecran": "Gros titre\\nsur 2 lignes", "pose": "etincelle"},
     {"type": "prompt", "voix": "texte lu", "etiquette": "PROMPT 1 · LE TRI", "prompt": "Texte exact du prompt", "pose": "clavier"}
   ]}
  Poses : profil, etincelle, clavier, emerveillee, pouce-leve
  Texte lu : "..." = pause marquée, "," = respiration.
Musique : déposer des .mp3 libres de droits dans reels/musique/ (une est tirée au hasard,
          mise en retrait automatiquement quand la voix parle).
"""
import asyncio, glob, json, math, os, random, shutil, subprocess, sys, tempfile, wave
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
W, H, FPS = 1080, 1920, 30
FOND = (19, 33, 60)
NUIT2 = (30, 44, 78)
ROSE, JAUNE, BLANC, GRIS = (255, 122, 156), (255, 216, 77), (246, 245, 250), (163, 167, 188)
PAUSE_SCENE = 0.6
Y_SOUS_TITRE = 1040          # bande des sous-titres (au-dessus de Louloutre)

def _ffmpeg():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg") or sys.exit("ffmpeg introuvable : pip install imageio-ffmpeg")
FF = _ffmpeg()

_polices = {}
def police(nom, taille):
    cle = (nom, taille)
    if cle not in _polices:
        f = os.path.join(RACINE, "branding/fonts", nom)
        _polices[cle] = ImageFont.truetype(f, taille) if os.path.exists(f) else ImageFont.load_default(taille)
    return _polices[cle]
GRAS, MOYEN, MONO = "Poppins-Bold.ttf", "Poppins-Medium.ttf", "DejaVuSansMono-Bold.ttf"

def ease(x):  # courbe d'animation douce
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

# ---------- 1. Voix ----------
async def _tts(texte, voix, vitesse, sortie, hauteur="-2Hz"):
    import edge_tts
    await edge_tts.Communicate(texte, voix, rate=vitesse, pitch=hauteur).save(sortie)

# Voix de Louloutre (choisir avec "preset" dans le script, ou REEL_PRESET=... en ligne de commande)
PRESETS = {
    "loutre_cartoon": {"voix": "fr-FR-VivienneMultilingualNeural", "vitesse": "-5%", "hauteur": 0, "effet": 1.10},
    "loutre_eloise":  {"voix": "fr-FR-EloiseNeural", "vitesse": "-4%", "hauteur": -4, "effet": None},
}

def _pct(v): return int(str(v).replace("%", "").replace("+", "") or 0)

def prosodie(i, n, sc, vitesse_base, hauteur_base=-2):
    """Varie légèrement débit et hauteur d'une scène à l'autre, comme un vrai narrateur :
    accroche plus énergique, prompts posés, fin plus chaleureuse."""
    if "ton" in sc: v, h = sc["ton"].get("vitesse", vitesse_base), sc["ton"].get("hauteur", "-2Hz"); return v, h
    base = _pct(vitesse_base); rnd = random.Random(i * 7 + 1)
    if i == 0:                  dv, dh = 4, 3      # accroche : plus vive, un peu plus haute
    elif i == n - 1:            dv, dh = -3, -1    # appel à l'action : plus posé
    elif sc.get("type") in ("prompt", "resultat"): dv, dh = -3, -3
    else:                       dv, dh = rnd.randint(-2, 4), rnd.randint(-3, 2)
    return f"{base + dv:+d}%", f"{dh + hauteur_base:+d}Hz"

def _prononciation():
    f = os.path.join(ICI, "prononciation.json")
    d = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    return {k: v for k, v in d.items() if not k.startswith("_")}

def phonetique(texte):
    import re
    for mot, dit in sorted(_prononciation().items(), key=lambda kv: -len(kv[0])):
        texte = re.sub(rf"(?<![\w-]){re.escape(mot)}(?![\w-])", dit, texte,
                       flags=0 if mot.isupper() else re.IGNORECASE)
    return texte

def voix_scene(texte, voix, vitesse, dossier, i, hauteur="-2Hz", effet=None):
    mp3, wav = os.path.join(dossier, f"s{i}.mp3"), os.path.join(dossier, f"s{i}.wav")
    if os.environ.get("REEL_SANS_VOIX") == "1":
        subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", f"{max(1.5, len(texte)/15)}", wav], check=True)
    else:
        asyncio.run(_tts(phonetique(texte), voix, vitesse, mp3, hauteur))
        coupe = "silenceremove=start_periods=1:start_threshold=-45dB"
        if effet: coupe = f"asetrate=24000*{effet},aresample=24000,atempo={1/effet:.4f}," + coupe
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "24000",
                        "-af", f"{coupe},areverse,{coupe},areverse", wav], check=True)
    with wave.open(wav) as w: return wav, w.getnframes() / w.getframerate()

# ---------- 2. Sous-titres mot à mot ----------
def mots_temps(texte, debut, duree):
    """Répartit les mots dans le temps (au prorata des lettres) et les groupe par 3."""
    mots = texte.replace("...", "").split()
    poids = [len(m) + 2 for m in mots]; total = sum(poids) or 1
    t, horo = debut, []
    for m, p in zip(mots, poids):
        d = duree * p / total; horo.append((t, t + d, m)); t += d
    return [horo[i:i+3] for i in range(0, len(horo), 3)]

# ---------- 3. Éléments graphiques ----------
_poses = {}
def pose(nom, taille):
    cle = (nom, taille)
    if cle not in _poses:
        im = Image.open(os.path.join(RACINE, "branding", f"louloutre-{nom}.png")).convert("RGB").resize((taille, taille), Image.LANCZOS)
        m = Image.new("L", im.size, 0)
        marge = int(taille * 0.07)
        ImageDraw.Draw(m).ellipse((marge, marge, taille - marge, taille - marge), fill=255)
        _poses[cle] = (im, m.filter(ImageFilter.GaussianBlur(taille * 0.07)))
    return _poses[cle]

def coller_alpha(fond, calque, alpha):
    if alpha >= 0.99: fond.alpha_composite(calque)
    elif alpha > 0.01:
        a = calque.getchannel("A").point(lambda v: int(v * alpha)); calque.putalpha(a); fond.alpha_composite(calque)

def _insecables(t):
    for c in (" :", " ?", " !", " ;", " »"): t = t.replace(c, "\u00a0" + c[1:])
    return t.replace("« ", "«\u00a0")

def renvoi_ligne(d, texte, f, largeur):
    lignes = []
    for para in _insecables(texte).split("\n"):
        cour = ""
        for mot in para.split(" "):
            essai = (cour + " " + mot).strip()
            if not cour or d.textlength(essai, font=f) <= largeur: cour = essai
            else: lignes.append(cour); cour = mot
        lignes.append(cour)
    return lignes

def lignes_titre(texte, taille_max=112, marge=140):
    """Prépare chaque ligne du titre comme une petite image (pour les animer séparément)."""
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    explicites = _insecables(texte).split("\n")
    t = taille_max
    while t > 72 and max(tmp.textlength(l, font=police(GRAS, t)) for l in explicites) > W - marge:
        t -= 4
    f = police(GRAS, t); lignes = renvoi_ligne(tmp, texte, f, W - marge)
    res = []
    for i, l in enumerate(lignes):
        couleur = JAUNE if (i == len(lignes) - 1 and len(lignes) > 1) else BLANC
        lw = int(tmp.textlength(l, font=f)) + 20
        im = Image.new("RGBA", (lw, int(t * 1.3)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 0), l, font=f, fill=couleur, stroke_width=4, stroke_fill=FOND)
        res.append(im)
    return res, t

def carte_prompt(etiquette, texte, style="prompt"):
    """Fond de la carte + lignes de texte (le texte est tapé progressivement au rendu)."""
    c = Image.new("RGBA", (W, 720), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    fe = police(GRAS, 38); lw = d.textlength(etiquette, font=fe)
    d.rounded_rectangle((70, 40, 70 + lw + 50, 110), 35, fill=ROSE if style == "prompt" else JAUNE)
    d.text((95, 50), etiquette, font=fe, fill=FOND)
    t = 46
    while t > 30:
        f = police(MONO if style == "prompt" else MOYEN, t); lignes = renvoi_ligne(d, texte, f, W - 260)
        if len(lignes) * t * 1.35 < 520: break
        t -= 2
    h = int(len(lignes) * t * 1.35 + (90 if style == "prompt" else 130))
    d.rounded_rectangle((70, 140, W - 70, 140 + h), 36, fill=BLANC if style == "prompt" else NUIT2, outline=None if style == "prompt" else JAUNE, width=4)
    d.ellipse((110, 172, 130, 192), fill=ROSE); d.ellipse((142, 172, 162, 192), fill=JAUNE); d.ellipse((174, 172, 194, 192), fill=(120, 200, 150))
    return c, lignes, f, t

# Particules d'ambiance (étincelles qui montent)
_rng = random.Random(3)
PARTICULES = [(_rng.uniform(40, W - 40), _rng.uniform(0, H), _rng.uniform(25, 70), _rng.uniform(3, 8),
               _rng.choice([JAUNE, ROSE, BLANC]), _rng.uniform(0, 6.28)) for _ in range(28)]

# ---------- 4. Rendu d'une image ----------
def image(t, scenes, groupes, duree):
    img = Image.new("RGBA", (W, H), FOND + (255,))
    i = next((k for k, s in enumerate(scenes) if s["debut"] <= t < s["fin"]), len(scenes) - 1)
    sc = scenes[i]; local = t - sc["debut"]; long = sc["fin"] - sc["debut"]
    accroche = (i == 0)
    # halo de fond
    r = 620 + 40 * math.sin(t * 1.3)
    halo = sc.setdefault("_halo", None)
    h = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0))
    ImageDraw.Draw(h).ellipse(((W/2 - r)/4, (1480 - r)/4, (W/2 + r)/4, (1480 + r)/4), fill=NUIT2 + (255,))
    img.alpha_composite(h.filter(ImageFilter.GaussianBlur(30)).resize((W, H)))
    d = ImageDraw.Draw(img)
    # particules
    for (x, y0, v, taille, coul, ph) in PARTICULES:
        y = (y0 - v * t) % H
        a = 0.35 + 0.35 * math.sin(t * 3 + ph)
        c = tuple(int(FOND[k] + (coul[k] - FOND[k]) * a) for k in range(3))
        d.ellipse((x - taille/2, y - taille/2, x + taille/2, y + taille/2), fill=c)

    sortie = 1 - ease((local - (long - 0.15)) / 0.15) if i < len(scenes) - 1 else 1

    # --- Louloutre : entre en glissant (côté alterné), pop, flottement
    taille = 640 if sc.get("type") in ("prompt", "resultat") else 760
    p, m = pose(sc.get("pose", "profil"), taille)
    entree_l = 1 if accroche else ease(local / 0.4)
    cote = -1 if i % 2 else 1
    x = (W - taille) // 2 + int(cote * (1 - entree_l) * 700)
    rebond = 1 + 0.07 * math.sin(min(local / 0.45, 1) * math.pi) * (0 if accroche else 1)
    tz = int(taille * rebond)
    if tz != taille: p, m = p.resize((tz, tz)), m.resize((tz, tz))
    y_flot = int(12 * math.sin(t * 2.4))
    img.paste(p, (x - (tz - taille) // 2, H - 60 - tz + y_flot), m)

    # --- Contenu
    if sc.get("type") in ("prompt", "resultat"):
        if "_carte" not in sc: sc["_carte"] = carte_prompt(sc.get("etiquette", "PROMPT"), sc.get("prompt") or sc.get("texte", ""), sc["type"])
        carte, lignes, f, tl = sc["_carte"]
        e = ease(local / 0.35)
        bloc = Image.new("RGBA", (W, 720), (0, 0, 0, 0)); bloc.paste(carte, (0, 0))
        dd = ImageDraw.Draw(bloc)
        total = sum(len(l) for l in lignes)
        tape = int(total * min(1, max(0, local - 0.3) / max(1.0, min(3.2, long * 0.65))))   # effet machine à écrire
        y, reste = 215, tape
        for l in lignes:
            part = l[:max(0, reste)]; reste -= len(l)
            dd.text((120, y), part, font=f, fill=FOND if sc["type"] == "prompt" else BLANC)
            if 0 <= reste + len(l) - len(part) and len(part) < len(l) and int(t * 3) % 2 == 0:
                cx = 120 + dd.textlength(part, font=f); dd.rectangle((cx + 2, y + 4, cx + 6, y + tl), fill=ROSE)
            y += tl * 1.35
            if reste <= 0: break
        echelle = 0.92 + 0.08 * e
        bw, bh = int(W * echelle), int(720 * echelle)
        bloc = bloc.resize((bw, bh))
        cal = Image.new("RGBA", (W, H), (0, 0, 0, 0)); cal.paste(bloc, ((W - bw) // 2, 170 + int((1 - e) * 60)))
        coller_alpha(img, cal, e * sortie)
    else:
        if "_lignes" not in sc: sc["_lignes"] = lignes_titre(sc["ecran"], 124 if accroche else 112, 240 if accroche else 140)
        lignes, tt = sc["_lignes"]
        y = 240 + (520 - len(lignes) * tt * 1.12) / 2
        for k, li in enumerate(lignes):
            if accroche:   # accroche : visible dès la 1re image, avec un « coup de zoom »
                e = 1.0; z = 1 + 0.10 * (1 - ease(local / 0.35))
            else:          # lignes qui arrivent une par une
                e = ease((local - 0.08 - k * 0.14) / 0.3); z = 0.85 + 0.15 * e
            lw, lh = int(li.width * z), int(li.height * z)
            l2 = li.resize((lw, lh)) if z != 1 else li.copy()
            cal = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            cal.paste(l2, ((W - lw) // 2, int(y - (lh - li.height) / 2 + (1 - e) * 50)))
            coller_alpha(img, cal, e * sortie)
            y += tt * 1.12

    d = ImageDraw.Draw(img)
    # flash de transition (2-3 images) au changement de scène
    if not accroche and local < 0.1:
        voile = Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - local / 0.1))))
        img.alpha_composite(voile); d = ImageDraw.Draw(img)
    # barre de progression
    d.rounded_rectangle((60, 70, W - 60, 82), 6, fill=NUIT2)
    d.rounded_rectangle((60, 70, 60 + (W - 120) * min(t / duree, 1), 82), 6, fill=ROSE)
    # sous-titres mot à mot
    g = next((g for g in groupes if g[0][0] <= t < g[-1][1]), None)
    if g:
        fs = police(GRAS, 64)
        mots = [m for _, _, m in g]
        x = (W - d.textlength(" ".join(mots), font=fs)) / 2
        y = Y_SOUS_TITRE + (90 if sc.get("type") in ("prompt", "resultat") else 0)
        for (a, b, mot) in g:
            lw = d.textlength(mot, font=fs); actif = a <= t < b
            if actif:
                pop = 1 + 0.1 * (1 - ease((t - a) / 0.12))
                d.rounded_rectangle((x - 12 * pop, y - 6 * pop, x + lw + 12 * pop, y + 82 * pop), 18, fill=ROSE)
            d.text((x, y), mot, font=fs, fill=BLANC, stroke_width=0 if actif else 5, stroke_fill=FOND)
            x += lw + d.textlength(" ", font=fs)
    fsg = police(MOYEN, 32); txt = "@louloute.ia"
    d.text(((W - d.textlength(txt, font=fsg)) / 2, H - 52), txt, font=fsg, fill=GRIS)
    return img.convert("RGB")

# ---------- 5. Assemblage ----------
def fabriquer(chemin_script):
    s = json.load(open(chemin_script, encoding="utf-8"))
    os.makedirs(os.path.join(ICI, "sortie"), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="reel_")
    preset = PRESETS.get(os.environ.get("REEL_PRESET") or s.get("preset", "loutre_cartoon"), {})
    voix = preset.get("voix", s.get("voix", "fr-FR-VivienneMultilingualNeural"))
    vitesse = preset.get("vitesse", s.get("vitesse", "+0%"))
    h_base, effet = preset.get("hauteur", -2), preset.get("effet")
    print("🎙  Voix...", flush=True)
    t, scenes, groupes, wavs = 0.35, [], [], []
    for i, sc in enumerate(s["scenes"]):
        v_sc, h_sc = prosodie(i, len(s["scenes"]), sc, vitesse, h_base)
        wav, d = voix_scene(sc["voix"], voix, v_sc, tmp, i, h_sc, effet)
        scenes.append({**sc, "debut": 0 if i == 0 else t, "fin": t + d + PAUSE_SCENE})
        groupes += mots_temps(sc["voix"], t, d)
        wavs.append((wav, t)); t += d + PAUSE_SCENE
    duree = t + 0.6; scenes[-1]["fin"] = duree
    voix_wav = os.path.join(tmp, "voix.wav")
    ent, fil = [], []
    for k, (w, debut) in enumerate(wavs):
        ent += ["-i", w]; fil.append(f"[{k}]adelay={int(debut*1000)}[a{k}]")
    fil.append("".join(f"[a{k}]" for k in range(len(wavs))) + f"amix=inputs={len(wavs)}:normalize=0,apad=whole_dur={duree}")
    subprocess.run([FF, "-y", "-loglevel", "error", *ent, "-filter_complex", ";".join(fil), voix_wav], check=True)
    # Voix « studio » + musique qui s'efface quand la voix parle
    audio = os.path.join(tmp, "mix.wav")
    voix_fx = "highpass=f=90,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,equalizer=f=3500:t=q:w=1:g=3,aecho=0.8:0.6:25:0.12,volume=1.4"
    musiques = glob.glob(os.path.join(ICI, "musique", "*.mp3"))
    if musiques:
        m = random.choice(musiques); print(f"🎵 Musique : {os.path.basename(m)}", flush=True)
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", voix_wav, "-stream_loop", "-1", "-i", m, "-filter_complex",
            f"[0]{voix_fx},asplit=2[v][sc];[1]volume=0.55,afade=t=in:d=0.4,afade=t=out:st={duree-1.2}:d=1.2[mu];"
            f"[mu][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95",
            "-t", f"{duree}", audio], check=True)
    else:
        print("🎵 Pas de musique (dépose des .mp3 dans reels/musique/)", flush=True)
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", voix_wav, "-af", voix_fx, audio], check=True)
    n = int(duree * FPS); print(f"🎬 Rendu de {n} images...", flush=True)
    suffixe = f"-{os.environ['REEL_PRESET']}" if os.environ.get("REEL_PRESET") else ""
    sortie = os.path.join(ICI, "sortie", f"{s['id']}{suffixe}.mp4")
    proc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie],
                            stdin=subprocess.PIPE)
    for k in range(n):
        proc.stdin.write(image(k / FPS, scenes, groupes, duree).tobytes())
    proc.stdin.close(); proc.wait(); shutil.rmtree(tmp, ignore_errors=True)
    print(f"✅ {sortie}  ({duree:.1f} s)")
    if s.get("legende"):
        open(sortie.replace(".mp4", ".txt"), "w", encoding="utf-8").write(s["legende"])
    return sortie

if __name__ == "__main__":
    fabriquer(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, "scripts", "reel-test.json"))

---
type: guide
reparto: tech
tags: [implementazione, pipeline, football, setup, make, youtube, tiktok, gemini, oracle]
status: draft
created: 2026-06-01
updated: 2026-06-01
---

# Setup Guide — World Cup 2026 Content Pipeline

Guida operativa step-by-step per configurare la pipeline fully automated di contenuti video per i Mondiali FIFA 2026.

Collegata a: [[Football_Content_Account_MOC]] — [[Architettura_Automazione_Pipeline_Social]]

**Tempo stimato:** 3-4 ore (una tantum). Tutti gli strumenti sono gratuiti.

---

## STEP 1 — Crea i 5 account necessari

### 1.1 football-data.org (dati partite)
1. Vai su football-data.org/client/register e registrati
2. Vai su **My Account > API Token** — copia il token
3. Verifica che il piano gratuito includa "FIFA World Cup 2026" nella lista competizioni
4. Salva il token come `FOOTBALL_DATA_API_KEY`

> Piano free: 10 chiamate/minuto. La pipeline ne fa 1/giorno — ampiamente sufficiente.

### 1.2 Google AI Studio (Gemini API key)
1. Vai su aistudio.google.com — accedi con Google
2. Clicca **"Get API key" > "Create API key"**
3. Salva la chiave come `GEMINI_API_KEY`

> Free tier Gemini: ~1.500 richieste/giorno — più che sufficiente per 1 post/giorno.

### 1.3 Oracle Cloud Free Tier (VPS gratuito)
1. Vai su cloud.oracle.com > **"Start for free"** (carta di credito richiesta, non addebitata)
2. Vai su **Compute > Instances > Create Instance**
   - Image: **Oracle Linux 8** (consigliato) o Ubuntu 22.04
   - Shape: **VM.Standard.E2.1.Micro** (Always Free)
   - Aggiungi la tua SSH public key
3. Copia l'indirizzo IP pubblico dell'istanza

### 1.4 Metricool (scheduling TikTok)
1. Vai su metricool.com e registrati gratis
2. **Connected Profiles > TikTok** — connetti il tuo account
3. Piano free: 50 post schedulati/mese — sufficiente per 1/giorno

### 1.5 Make.com (orchestrazione)
1. Vai su make.com e registrati gratis
2. Piano free: 1.000 operazioni/mese — sufficiente per la pipeline

---

## STEP 2 — Configura il VPS Oracle Cloud

Connettiti al VPS dal terminale:
```bash
ssh opc@TUO_IP_PUBBLICO      # Oracle Linux
# oppure
ssh ubuntu@TUO_IP_PUBBLICO   # Ubuntu
```

### 2.1 Installa Python, dipendenze, FFmpeg e font

**Ubuntu 22.04 (consigliato):**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3-pip ffmpeg fonts-dejavu

# Font 1 — Stadio Broadcast: Bebas Neue (titoli) + Inter (corpo)
sudo apt install -y fonts-bebas-neue

# Inter: download manuale da Google Fonts
mkdir -p ~/.local/share/fonts
wget -O /tmp/inter.zip "https://fonts.google.com/download?family=Inter"
unzip /tmp/inter.zip -d /tmp/inter_fonts
cp /tmp/inter_fonts/*.ttf ~/.local/share/fonts/
fc-cache -fv
```

**Oracle Linux 8:**
```bash
sudo dnf update -y
sudo dnf install -y python3.11 python3.11-pip epel-release ffmpeg
sudo dnf install -y dejavu-sans-fonts dejavu-fonts-common

# Bebas Neue + Inter: copia manualmente i .ttf nella home fonts
mkdir -p ~/.local/share/fonts
# Carica BebasNeue-Regular.ttf e Inter-Regular.ttf via FileZilla in ~/.local/share/fonts/
fc-cache -fv
```

**Verifica font installati:**
```bash
fc-list | grep -iE "bebas|inter"
```
> Se i font non compaiono, il codice usa DejaVu come fallback — il video funziona ma con qualità visiva ridotta.

### 2.2 Carica il codice sul VPS

Dal tuo computer locale:
```bash
scp -r /percorso/locale/implementation/ opc@TUO_IP_PUBBLICO:/home/opc/wc2026/
```

Oppure usa FileZilla (SFTP) per trasferire i file graficamente.

### 2.3 Installa le dipendenze Python
```bash
cd /home/opc/wc2026/
pip3 install -r requirements.txt
pip3 list | grep -E "Pillow|requests|feedparser|google"
```

---

## STEP 3 — Configura le variabili d'ambiente

```bash
nano ~/.bashrc
```

Aggiungi in fondo (sostituisci con le chiavi reali):
```bash
export FOOTBALL_DATA_API_KEY="la_tua_api_key_football_data"
export GEMINI_API_KEY="la_tua_api_key_gemini"
```

Salva (Ctrl+O, Invio, Ctrl+X) e ricarica:
```bash
source ~/.bashrc
echo $FOOTBALL_DATA_API_KEY   # deve mostrare la chiave
echo $GEMINI_API_KEY           # deve mostrare la chiave
```

---

## STEP 4 — Test locale sul VPS

```bash
cd /home/opc/wc2026/

# Test singoli moduli
python3 fetch_data.py
python3 generate_caption.py

# Pipeline completa senza video (più veloce)
python3 main.py --dry-run

# Pipeline completa con video (2-5 minuti)
python3 main.py
```

Output atteso in `output/YYYY-MM-DD/`:
- `wc2026_YYYY-MM-DD.mp4` — il video
- `metadata.json` — dati della sessione (hook, caption, hashtag, partita)

---

## STEP 5 — Setup Make.com (trigger giornaliero)

1. Make.com > **Scenarios > Create a new scenario**
2. Modulo 1: **Schedule**
   - Interval: Every day
   - Time: 07:00 (adatta al tuo fuso orario)
3. Modulo 2: **SSH > Execute a command**
   - Host: `TUO_IP_PUBBLICO`
   - Port: `22`
   - Username: `opc`
   - Authentication: Private Key (incolla la tua chiave SSH privata)
   - Command:
     ```
     cd /home/opc/wc2026 && source ~/.bashrc && python3 main.py >> /home/opc/wc2026/pipeline.log 2>&1
     ```
4. Modulo 3 (opzionale): **Email** — notifica al termine
5. **Save** > **Run Once** per testare > Toggle **ON**

---

## STEP 6 — YouTube Data API v3 (pubblicazione automatica)

### 6.1 Crea progetto Google Cloud
1. console.cloud.google.com > Nuovo progetto (es. "WC2026Pipeline")
2. **APIs & Services > Library** > cerca **"YouTube Data API v3"** > Enable

### 6.2 Crea credenziali OAuth
1. **APIs & Services > Credentials > Create Credentials > OAuth client ID**
2. Application type: **Desktop app**
3. Scarica il JSON > salvalo come `youtube_oauth_credentials.json` nella cartella del progetto

> Lo script di upload YouTube (`youtube_uploader.py`) è previsto come sviluppo successivo. Nel frattempo carica manualmente da YouTube Studio.

### 6.3 Upload manuale nel frattempo
1. Scarica il video dal VPS con FileZilla
2. Carica su YouTube Studio come Short (9:16, max 60s)
3. Incolla caption e hashtag dal file `metadata.json`

---

## STEP 7 — Metricool (pubblicazione TikTok)

### Workflow giornaliero (~5 minuti)
1. Scarica il video dalla cartella `output/YYYY-MM-DD/` via FileZilla
2. In Metricool: **Planning > New Post > TikTok**
3. Carica il video, incolla caption da `metadata.json`
4. Schedula per le 18:00-20:00 (picco di engagement)

> Alternativa fully automated: verifica se Make.com ha un modulo Metricool attivo su make.com/integrations/metricool alla data di lancio.

---

## STEP 8 — Checklist pre-lancio (eseguire 24h prima dell'11 giugno)

- [ ] `python3 fetch_data.py` restituisce dati reali (non fallback)
- [ ] `python3 generate_caption.py` genera testo coerente con la partita
- [ ] `python3 main.py` completa senza errori e produce un MP4
- [ ] Il video si apre correttamente (1080x1920, 15 secondi)
- [ ] Make.com esegue lo scenario (Run Once) senza errori
- [ ] `pipeline.log` viene aggiornato dopo ogni esecuzione
- [ ] Il video caricato su YouTube è classificato come Short
- [ ] Il video schedulato su Metricool viene pubblicato su TikTok
- [ ] Watermark `ACCOUNT_WATERMARK` in `video_generator.py` aggiornato con il nome account reale

---

## Problemi comuni

| Problema | Causa | Soluzione |
|---|---|---|
| `FFmpeg non trovato` | FFmpeg non installato | `sudo dnf install ffmpeg` |
| `403 da football-data.org` | Piano non include WC 2026 | Verifica su football-data.org/person/login |
| `GEMINI_API_KEY non impostata` | Variabile non caricata | `source ~/.bashrc` |
| Testo video a bassa qualità | Font TrueType non trovato | `sudo dnf install dejavu-sans-fonts` |
| Video non classificato come Short | Durata > 60s o formato errato | Verifica: 1080x1920, 15 secondi |
| Make.com SSH fallisce | Chiave SSH errata | Rigenera con `ssh-keygen`, aggiorna in Make |
| Gemini restituisce errore modello | Modello cambiato dopo agosto 2025 | Aggiorna `MODEL_NAME` in `generate_caption.py` con il modello free tier attuale su ai.google.dev/gemini-api/docs/models |

---

## Fonti

- football-data.org — API Documentation — football-data.org/documentation/quickstart — knowledge cutoff agosto 2025
- Google AI — Gemini API Quickstart — ai.google.dev/gemini-api/docs/quickstart — knowledge cutoff agosto 2025
- Oracle Cloud — Always Free Resources — docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm — knowledge cutoff agosto 2025
- Make.com — SSH Module — docs.make.com/en/modules/ssh — knowledge cutoff agosto 2025
- Google Developers — YouTube Data API v3 — developers.google.com/youtube/v3/docs/videos/insert — knowledge cutoff agosto 2025
- Metricool — Help Center — help.metricool.com — knowledge cutoff agosto 2025

> Knowledge cutoff agosto 2025. Verifica API, modelli e ToS sui siti ufficiali prima del lancio.

# How to upload nternet-Link V4 to GitHub

Everything in this folder is ready to publish to your repo
**github.com/OtterCadGH/nternet-Link**. The plan is to put it all in a
`v4/` folder on a new branch called `v4`, so nothing on `main` changes and
you get a pull request you can review and merge whenever you like.

Nothing here contains API keys — the firmware keeps secrets on the device,
not in the source. Safe to make public.

Pick ONE of the three methods below. If you're not a git person, use
**Method A (website)** — it needs no tools.

---

## Method A — GitHub website (easiest, no tools)

1. Go to **https://github.com/OtterCadGH/nternet-Link**.
2. Click the branch dropdown (says `main`), type `v4`, and click
   **"Create branch: v4 from main"**.
3. Make sure you're now on the `v4` branch (the dropdown shows `v4`).
4. Click **Add file → Upload files**.
5. In your file explorer, open this folder and **drag the whole
   `nternet-link-v4` folder** into the upload box. GitHub keeps the
   subfolders. (If drag-drop of a folder doesn't take, drag the *contents*
   in — `README.md`, `src/`, `hardware/`, etc.)
   - Tip: rename the folder to `v4` before dragging, so it lands as
     `v4/...` in the repo. Or upload into a path by typing `v4/` at the top
     of the upload page's filename bar.
6. Scroll down, leave "Commit directly to the v4 branch" selected, add a
   commit message like `Add nternet-Link V4`, and click **Commit changes**.
7. GitHub shows a banner offering to **Compare & pull request** — click it
   to open a PR from `v4` into `main`. Merge it whenever you're ready.

Big binary files (the PDFs, PNG) upload fine this way.

---

## Method B — Git on your computer (cleanest; preserves everything)

Open a terminal (Git Bash, macOS Terminal, or Linux shell) with git
installed and signed in to GitHub, then:

```bash
# 1. clone your repo (skip if you already have it)
git clone https://github.com/OtterCadGH/nternet-Link.git
cd nternet-Link

# 2. make the v4 branch
git checkout -b v4

# 3. copy this whole folder in as v4/
#    (replace the path with wherever you saved nternet-link-v4)
mkdir v4
cp -r /path/to/nternet-link-v4/* v4/
#    Windows PowerShell:  Copy-Item -Recurse C:\path\to\nternet-link-v4\* v4\

# 4. commit and push
git add v4
git commit -m "Add nternet-Link V4: firmware, protocol, GUI simulator, PCBs"
git push -u origin v4
```

Then open the repo on GitHub and click **Compare & pull request**.

---

## Method C — GitHub Desktop (GUI, no command line)

1. Install **GitHub Desktop** (desktop.github.com) and sign in.
2. **File → Clone repository →** pick `OtterCadGH/nternet-Link`.
3. **Branch → New branch →** name it `v4`.
4. In your file explorer, copy the `nternet-link-v4` folder into the cloned
   repo folder, renamed to `v4`.
5. GitHub Desktop lists the new files. Type a summary
   (`Add nternet-Link V4`) and click **Commit to v4**.
6. Click **Push origin**, then **Create Pull Request**.

---

## What you're uploading

```
v4/
├── README.md                 project overview
├── PROJECT-STATUS.md         status + next steps
├── UPLOAD-INSTRUCTIONS.md    this file
├── platformio.ini            firmware build targets
├── include/ , src/           ESP32 firmware (C++)
├── calculator/               TI-Nspire Lua client + demo
├── docs/PROTOCOL.md          wire protocol spec
├── tools/gui_simulator.html  browser GUI simulator (mini-Claude UI)
├── test/                     host-side protocol tests
└── hardware/
    ├── PCB-DESIGN.md
    └── kicad/                4 board variants + generators + verifier
        ├── CAPTURE-PLAN.md
        ├── nlink-proto/  nlink-stick/  nlink-cam/  nlink-lite/
        └── lib/           vendored C3-MINI-1 symbol/footprint
```

## After it's up (optional polish)

- On GitHub, set the repo's default view or add a link to `v4/README.md`
  from the top-level `README.md` so visitors find V4.
- The GUI simulator (`v4/tools/gui_simulator.html`) can be published as a
  live page with **GitHub Pages** (Settings → Pages → deploy from branch)
  so people can try it in a browser without downloading.
- When V4 is ready to be the main version, merge the `v4` PR into `main`.

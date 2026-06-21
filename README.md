# ReelGrants — Launch Kit (Perch Scout #1)

**What this is:** the demand-validation probe for the first Perch Scout — personalized film-grant alerts. The niche was chosen via a 6-agent evidence gauntlet (see `vault/06-research/` + `vault/02-product/scout-01-film-grants.md`). This folder is everything needed to put a real, useful free grant tracker in front of filmmakers and measure whether they want alerts.

**Files**
- `index.html` — the probe landing page + free live grant tracker (single file, deploy anywhere).
- `grants.json` — 39 real, verified film/creator funds (the tracker content + future engine seed).
- `README.md` — this file.

---

## The rule we're not breaking
**We do NOT build the paid engine until demand is proven.** Proof = **25+ "alert me" signups from one genuine community post.** This probe is the gate. If it passes → build the engine (`vault/04-engineering/grant-adapter.md`). If it flops after a fair test → switch niche (Scout #2 = real-estate investor alerts), keep the engine + probe. That's the Perch model: validate cheap, build once.

---

## NICK'S STEPS (the only human-required part — ~30–45 min total)

### 1. Pick + register a domain (~$10–12 of the $100)
Working name is **ReelGrants** — ⚠️ **verify availability first** (the `___Scout` family name "GrantScout" is taken many times over; don't reuse it). Check the name + domain on Namecheap. If `reelgrants.com` is taken, fallbacks in priority order: **getreelgrants.com**, **reelgrants.org**, **grantreel.com**, **filmgrantradar.com**. Whatever you pick, it's a 1-line swap in the HTML (the logo text + title).

### 2. Wire the email capture (free, ~5 min)
The form currently posts to a placeholder. Create a free **Formspree** form (formspree.io → new form → copy its endpoint like `https://formspree.io/f/abcwxyz`) and replace **both** occurrences of `https://formspree.io/f/REPLACE_ME` in `index.html`. (Alternatives that also work: a Tally form, a Google Form, or Resend — but Formspree is the least friction for a static page.) Signups will land in your email. The form already captures **email + discipline**, so you'll see *what kind* of filmmaker is raising their hand.

### 3. Deploy (free, ~5 min)
Easiest: **Netlify Drop** — go to app.netlify.com/drop and drag the `reelgrants` folder in. Live URL instantly; point your domain at it. (Or `vercel` / GitHub Pages — same result. The Perch stack default is Vercel.)

### 4. Seed it in ONE community (the distribution atom — value-first, NOT a sales pitch)
Post the **free tracker** as a genuinely helpful resource. Drafts below — use your own filmmaker voice, post from a real account, and **engage in the comments** (that's where trust + signups come from). Pick ONE to start (r/Filmmakers or r/Documentary), measure, then do the second.

### 5. Watch signups → that's the gate
25+ from one post = strong signal → tell me and I'll build the engine + Stripe billing. Under ~10 after a fair, well-engaged post = the niche or the pitch is wrong → we switch to Scout #2. **Stripe isn't needed until the gate passes** (you already have it pending — wire it then, not now).

---

## Drafted community seed posts (value-first)

**Reddit — r/Filmmakers or r/Documentary** (title + body):

> **Title:** I got tired of missing film-grant deadlines, so I built a free tracker that keeps the open ones in one place
>
> Every season there's a giant list of grants floating around, but they go stale fast and I'd always find out about the perfect one *after* it closed. I put together a free, always-updating tracker of film grants/fellowships/funds (Sundance, Firelight, Catapult, SFFILM, IDA, state arts councils, etc.) — you can filter by what you make (doc / narrative / screenwriting / animation / shorts) and see what's actually open right now vs. when it typically reopens.
>
> It's free to use here: [your URL]
>
> I'm also testing an optional "alert me about grants I qualify for + nudge me before the deadline" feature — if that'd be useful, there's a signup, but the tracker itself is free and I'll keep it updated. Would love feedback on which funds I'm missing — drop them and I'll add them.

**A comment on a No Film School / StudioBinder grant-list article, or a filmmaker Discord/FB group:**

> If it helps anyone — I keep a free running tracker of which of these are actually open right now (and when the closed ones typically reopen), filterable by format: [your URL]. Trying to make it so nobody misses a deadline again. Open to additions.

**Rules of the road (so it lands as helpful, not spam):**
- Lead with the **free** resource. The alert signup is secondary.
- Don't post the same text in 5 places same day — one community, engage, then the next.
- Reply to every "you're missing X grant" — adding their suggestion = instant goodwill + a better product.
- Read each community's self-promo rules first.

---

## What I (Claude) already did
- Killed 4 weaker niches with evidence (reseller alerts, appointment slots, bourbon, liquor licenses).
- Chose film-grant alerts; bullet-tested it (confirmed real WTP, found the "personalization not a list" wedge, confirmed no free comprehensive incumbent, rejected the dead "GrantScout" name).
- Compiled 39 real, verified funds.
- Built this probe + tracker, the scout spec, and the engine adapter design (ready to build on a "go").

The money is gated behind real human demand — by design. Your move is steps 1–4 above; then the signups tell us whether to build or pivot.

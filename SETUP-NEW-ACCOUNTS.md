# ReelGrants — Separate-Accounts Setup (keeps this 100% detached from TavaTrack)

You said (correctly) you don't want this sharing TavaTrack's GitHub or Supabase. Here's the
shortest path to give this venture its own clean infrastructure. **Your part ≈ 15 minutes.**
Everything is already built and waiting; these accounts are the only blocker.

---

## What I need from you (hand me these 3 things and I do the rest)

1. **A new GitHub account** (for hosting the site free via GitHub Pages).
   - Sign up at github.com with a fresh email (or a `+reelgrants` alias).
   - Then either: (a) run `gh auth login` in this terminal and pick the new account, **or**
     (b) create an empty public repo named `reelgrants` and tell me its URL. I'll push + enable Pages.
   - Result: a live site at `https://<newuser>.github.io/reelgrants/` (custom domain later).

2. **A new Supabase account + project** (the free capture backend — stores email signups).
   - Sign up at supabase.com with the fresh email → "New project" (Free plan, $0).
   - Open the project's **SQL Editor**, paste the contents of `signups.sql` (in this folder), Run.
   - Go to **Project Settings → API** and copy two values:
     - **Project URL** (looks like `https://abcd1234.supabase.co`)
     - **anon / publishable key** (the public one — safe to put in the website; it can only INSERT, not read)
   - Paste those two values to me (or into the two blank lines at the bottom of `index.html`:
     `const SUPABASE_URL` and `const SUPABASE_ANON_KEY`). That's the whole wiring.

3. **(Later, only after signups validate)** a way to collect payment — a new Stripe account.
   Not needed yet. We wire it the day the demand gate passes.

> Google account: not needed for any of the above. Only relevant if we later send alert
> emails from a branded address — we'll cross that bridge when there's demand.

---

## After I have those — what happens automatically (no work from you)
1. I paste the Supabase URL + key into the page and confirm a test signup lands in your table.
2. I push the site to the new GitHub and turn on Pages → you get a live URL.
3. I hand you the live URL + the drafted community post (in `README.md`).
4. **You do the one irreducible human thing:** post the free tracker in r/Filmmakers (or r/Documentary),
   in your own voice, and reply to comments. That's the part no AI can or should fake.
5. Signups roll into your Supabase table. **Gate = 25+ from one good post.**
   - Pass → I build the live engine (daily grant-poller + the matching core that already works + email alerts) and wire Stripe.
   - Flop after a fair test → we pivot the same machine to Scout #2 (real-estate investor alerts). Nothing wasted.

---

## Why it's set up this way
- **Free to run:** GitHub Pages + Supabase free tier + the matching engine (pennies) = ~$0 until there's revenue. Your $100 is barely touched (just a domain when you want one).
- **Fully detached:** new GitHub, new Supabase, new email — zero overlap with TavaTrack.
- **Safe by design:** the website only holds the *public* anon key, which can add a signup but cannot read the list. You read signups in the Supabase dashboard.

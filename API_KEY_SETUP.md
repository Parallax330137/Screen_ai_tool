# Getting a Gemini API Key

This tool needs a Google Gemini API key to work. Here's how to get one, and
how to avoid the two gotchas that usually trip people up.

## 1. Create a key

1. Go to **[aistudio.google.com](https://aistudio.google.com/)**.
2. Sign in with any Google account.
3. Click **"Get API key"** (usually top-left, or under the menu).
4. Click **"Create API key."**
5. Copy the key it shows you — it looks like `AIzaSy...` or `AQ....`.

That's it. No credit card, no billing setup required for the free tier.

## 2. Not the same as a Gemini app subscription

If you (or someone in your family) pays for a Gemini/Google One AI plan,
that subscription does **not** give you API access. It's a separate
product. The steps above always work regardless of any app subscription,
and are free on their own.

## 3. Put the key in the tool

Two ways:

**Easiest — control panel:**
```
python control_panel.py
```
Go to the "API Keys & Models" tab, paste your key into a row, click Save.

**Manual:**
```
cp config.example.json config.json
```
Open `config.json`, find `"gemini_api_keys"`, replace the placeholder with
your real key:
```json
"gemini_api_keys": ["AIzaSy...your-real-key-here"]
```

## 4. Adding more than one key

Click **"+ Add key"** in the control panel as many times as you want, or
add more entries to the `gemini_api_keys` list manually. `screen_ai.py`
automatically rotates to the next key (and the next model, if you've listed
more than one) whenever it hits a quota or rate-limit error.

**Important caveat:** Gemini's free tier quota is scoped **per Google Cloud
project**, not per individual key. If you generate several keys from the
same Google account without creating separate Cloud projects, they usually
all draw from one shared quota pool — adding more keys won't actually raise
your daily limit in that case. To get a genuinely separate pool, either:
- use keys from different Google accounts, or
- create separate projects under Google Cloud Console for each key, or
- enable billing on one project (removes the free-tier cap entirely — for
  light use like this tool, cost is typically fractions of a cent per
  request).

## 5. Errors you might see, and what they mean

**`429 ... quota exceeded ... free_tier_requests ... limit: 20`**
You've hit the daily free-tier cap for that specific model on that project.
Not a bug — either wait for the daily reset, add a key from a genuinely
separate project/account, or switch to a model with its own separate quota
(add more entries to `model_names`).

**`404 ... model is no longer available to new users`**
That specific model name has been deprecated or restricted for your
account. Run this to see which models your key can actually call:
```
python -c "import google.generativeai as genai, json; genai.configure(api_key=json.load(open('config.json'))['gemini_api_keys'][0]); [print(m.name) for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]"
```
Pick one with "flash" in the name (cheapest/fastest tier) and put it in
`model_names`.

## 6. Keep your key private

Never commit `config.json` to git — it's already in `.gitignore` for this
reason. If a key ever ends up somewhere public (a chat log, a commit, a
screenshot), treat it as compromised: go back to aistudio.google.com and
delete/regenerate it. Removing a file in a later commit does not remove it
from git history, so prevention beats cleanup here.

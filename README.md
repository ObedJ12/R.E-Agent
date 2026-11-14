# R.E-Agent

Personal AI deal-analysis agents for real estate investing and wholesaling.
It covers what Bricked.ai does, plus lead lists, outreach, zoning and blueprint reading.

**Status: phase 1 of 6 — Comps and Underwriting.**

| Phase | Agent | Status |
| --- | --- | --- |
| 1 | Comps and Underwriting | ✅ working |
| 2 | Property Research (liens, tax, flood) | next |
| 3 | Lead List (motivated sellers + score) | planned |
| 4 | Outreach (skip trace, DNC scrub, approve-before-send) | planned |
| 5 | Zoning Rights | planned |
| 6 | Blueprint Reader | planned |

## What phase 1 does

Type an address and get:

- **Comps**: pulled within your radius and time window, with bad matches filtered out (too big or small, too far, too old, active listings). Each exclusion shows the reason.
- **Adjustments**: each comp's price is adjusted toward your property for square feet, beds, baths and age.
- **Distressed vs renovated split**: cheap as-is sales are separated from renovated ones, so they don't drag down the ARV.
- **ARV and as-is value**, with a confidence rating.
- **Repair estimate** by condition (C1–C6), with line items and a local cost multiplier.
- **Photo condition scoring** (optional): upload listing photos and Claude rates the condition and lists the visible issues.
- **Exit math**: wholesale MAO (70% rule plus your fee), fix and flip, rental and BRRRR.
- **Deal memo** (optional): a short write-up from Claude with a verdict, the best exit and the main risks.
- **PDF report** you can download and send to buyers.

## Run it

```bash
git clone https://github.com/ObedJ12/R.E-Agent.git
cd R.E-Agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then add your keys (optional at first)
streamlit run app.py
```

With no keys it runs on **demo data**, so you can try it right away.

### Keys (in `.env`)

| Key | What it turns on | Where to get it | Cost |
| --- | --- | --- | --- |
| `RENTCAST_API_KEY` | Live property facts, comps, rent estimates | [app.rentcast.io](https://app.rentcast.io/app/api) | Free tier: 50 calls/month |
| `ANTHROPIC_API_KEY` | Photo condition scoring and the deal memo | [console.anthropic.com](https://console.anthropic.com/) | Pay per use, usually a few cents per deal |

Each analyzed address uses about 3 RentCast calls. Responses are cached for 30 days in `.cache/`, so re-running a deal costs nothing.

## Known limits

- RentCast comps are **listings, not recorded closings**. "Inactive" usually means sold, and the price is the last list price. MLS sold data (phase 2+) will tighten this up.
- Repair costs are national mid-range defaults. Set the cost multiplier for your market and check line items against your contractor's numbers.
- Estimates only. Verify before making offers.

## Layout

```
app.py                  Streamlit UI
re_agents/
  underwrite.py         Comps & Underwriting agent: address in, DealReport out
  comps.py              comp filtering, adjustments, ARV / as-is
  repairs.py            rehab estimate by condition
  calculators.py        wholesale, flip, rental, BRRRR
  ai.py                 Claude: photo condition + deal memo
  report.py             PDF export
  data/rentcast.py      RentCast client (cached)
  data/sample.py        offline demo data
tests/                  pytest suite (python -m pytest)
```

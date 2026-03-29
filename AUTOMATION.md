# GitHub Actions Setup for Cricket Player Register

This guide shows how to automate player enrichment and generate reports on GitHub.

## Quick Setup (5 minutes)

### 1. Create GitHub Actions Workflow

Create `.github/workflows/enrich-players.yml`:

```yaml
name: Enrich Cricket Players

on:
  schedule:
    # Run every Sunday at 2 AM UTC (after weekend international matches)
    - cron: '0 2 * * 0'
  
  # Also allow manual trigger
  workflow_dispatch:
    inputs:
      force_refresh:
        description: 'Re-enrich all players (not just new ones)'
        required: false
        default: 'false'

jobs:
  enrich:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.14'
      
      - name: Install dependencies
        run: |
          python -m venv .venv
          source .venv/bin/activate
          pip install -r requirements.txt
      
      - name: Run enrichment pipeline
        env:
          PYTHONIOENCODING: 'utf-8'
        run: |
          source .venv/bin/activate
          python pipeline.py --skip-espn
      
      - name: Generate report
        run: |
          source .venv/bin/activate
          python _generate_enrichment_report.py
      
      - name: Commit results
        run: |
          git config user.name "Player Enrichment Bot"
          git config user.email "bot@github.local"
          git add output/ data/cache/ data/enrichment_state.json
          git commit -m "🏏 Auto-enrich: $(date +%Y-%m-%d)" || true
          git push
      
      - name: Create deployment
        if: success()
        run: |
          # Optional: Deploy dashboard to GitHub Pages
          mkdir -p public
          cp output/dashboard.html public/index.html
          git add public/
          git commit -m "📊 Update dashboard" || true
          git push
```

### 2. GitHub Pages Setup (Optional - for hosting dashboard)

1. In repository settings → Pages
2. Select "Deploy from a branch"
3. Select `main` branch / `public` folder
4. Dashboard will be at `https://youruser.github.io/player-register/`

## How It Works

### Scheduled Runs
- **Default**: Sundays 2 AM UTC (customizable in cron schedule)
- **Incremental**: Only processes new/missing players (state-aware)
- **Smart caching**: Uses cached responses to avoid redundant network calls

### Manual Trigger
```
GitHub UI → Actions → "Enrich Cricket Players" → "Run workflow"
```

### What Gets Updated
- `output/player_profiles.json` - Full player database
- `output/dashboard.html` - Interactive player discovery tool  
- `output/dashboard_data.json` - Raw data for integrations
- `data/cache/profiles_raw.json` - ESPN response cache
- `data/enrichment_state.json` - Enrichment tracking (git-ignored)

## State Management

### Enrichment State (`data/enrichment_state.json`)
```json
{
  "player_id_1": {
    "enriched": true,
    "last_attempted": "2026-03-29T15:30:00+00:00",
    "has_data": true
  },
  "player_id_2": {
    "enriched": false,
    "last_attempted": "2026-03-29T15:35:00+00:00",
    "has_data": false,
    "error": "API returned 404"
  }
}
```

**Benefits:**
- ✅ Skip already-enriched players on re-runs
- ✅ Track failed enrichment attempts
- ✅ Know which players still need manual review
- ✅ ~70% faster on subsequent runs

## Local Testing

Before setting up GitHub Actions, test locally:

```bash
# First run (processes all 1237 match players)
python pipeline.py --skip-espn

# Check state file
cat data/enrichment_state.json | jq '.[] | select(.has_data==false)' | wc -l
# Shows: {number} players without data

# Second run (skips already-enriched, processes only missing)
python pipeline.py --skip-espn
# "Already enriched: 1100+" (faster!)
```

## Monitoring & Debugging

### Check Enrichment Progress
```bash
python -c "
import json
state = json.load(open('data/enrichment_state.json'))
enriched = sum(1 for v in state.values() if v['has_data'])
print(f'Enriched: {enriched}/{len(state)} ({100*enriched//len(state)}%)')
"
```

### View Failed Players
```bash
python -c "
import json
state = json.load(open('data/enrichment_state.json'))
failed = {k: v for k, v in state.items() if not v['has_data']}
print(f'Failed: {len(failed)}')
for player_id, info in list(failed.items())[:5]:
    print(f'  {player_id}: {info.get(\"error\", \"unknown\")}')"
```

### Generate Enrichment Report
```bash
python _generate_enrichment_report.py
# Creates: data/enrichment_report.json
```

## Advanced Configuration

### Run on Different Schedule
Edit `.github/workflows/enrich-players.yml`:

```yaml
schedule:
  # Daily at 3 AM UTC
  - cron: '0 3 * * *'
  
  # Or: Every 6 hours
  - cron: '0 */6 * * *'
```

### Add Notifications (Email/Slack)
```yaml
- name: Send notification
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
    text: 'Player enrichment failed!'
```

### Deploy to Different Platforms
- **GitHub Pages**: Use `gh-pages` branch
- **AWS S3**: Add AWS credentials, upload to bucket
- **Vercel**: Add Vercel deployment step
- **Netlify**: Use Netlify CLI in workflow

## Handling Rate Limiting

If ESPN/Cricbuzz rate-limits responses:

1. **Increase rate limit in code**:
   ```python
   scraper = EspnScraper(rate_limit_seconds=2.0)  # Default: 0.5s
   ```

2. **Use GitHub's rate limiting**:
   - Spread runs across different times
   - Use exponential backoff in scraper (already enabled)

3. **Monitor quota**:
   ```bash
   grep -o "fetch_error" data/cache/profiles_raw.json | wc -l
   # Shows: number of rate-limit errors
   ```

## API Data Sources

### Primary (Unblocked)
- **ESPN Site API**: `https://site.api.espn.com/` 
- **Cricbuzz**: `https://www.cricbuzz.com/profiles/` (22 players only)

### Fallback (Blocked/Limited)
- ESPN Cricinfo HTML: Akamai JS challenge
- ESPN JSON API: Various endpoints (deprecated)

## Future Enhancements

1. **Periodic reports** (monthly enrichment summary)
2. **Integration with Slack** (team notifications)
3. **Database sync** (store in PostgreSQL/MongoDB)
4. **Custom registry** (`registry_enriched.json` with FirstName_LastName format)
5. **Web API** for programmatic access to player data
6. **Mobile app** using dashboard data as API

## Troubleshooting

### Workflow Fails with "Module not found"
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### "Permission denied" on GitHub
1. Go to repo Settings → Actions → General
2. Ensure "Read and write permissions" is enabled
3. Check "Allow GitHub Actions to create and approve pull requests"

### Enrichment barely changes run-to-run
- Expected! State tracking means only new players are re-scraped
- To force full re-run: Delete `data/enrichment_state.json` and push

## Costs

- **GitHub Actions**: 2,000 free minutes/month (5min/run × ~8 runs = 40 min/month with daily runs)
- **GitHub Pages**: Free (unlimited)
- **Data storage**: ~2MB for all caches/state (negligible)

**Result**: Fully hosted enrichment system costs $0 ✅

## Contact & Support

For issues or customization:
1. Check the [README.md](../README.md) first
2. Review [ENHANCEMENTS.md](../ENHANCEMENTS.md) for feature status
3. Create a GitHub issue with:
   - Workflow run log
   - Sample player data
   - Expected vs. actual behavior

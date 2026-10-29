# Sources, permissions and licensing

The app stores **metadata only**: canonical URL, title, a short excerpt (≤ 400 characters),
publisher, publication time and tags, then writes original summaries. It never stores full
publisher articles or images, never bypasses paywalls or access controls, honours robots.txt
(RFC 9309) and paces requests per host. Live fetching is off until
`ENABLE_LIVE_INGESTION=true`; set `INGESTION_CONTACT` so the crawler identifies itself as
`Mozilla/5.0 (compatible; AajkeKiSceneBot/0.1; +<contact>)`.

**Before any public release, review each source's current terms** - this table records what
was checked during development (2026-10-29), not legal advice.

| Source | Tier | Endpoint | Default | Checked | Notes |
|---|---|---|---|---|---|
| PIB (Press Information Bureau) | A | `https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1` | on | Akamai **403** to automated clients from the dev network | Government releases; official status does not make every asset unrestricted. The fetcher records the 403 and never tries to bypass it. |
| RBI press releases | A | `https://www.rbi.org.in/pressreleases_rss.xml` | on | 200, valid RSS | Feed states "Copyright Reserve Bank of India. All Rights Reserved." Links + short excerpts + attribution only. |
| UN News | A | `https://news.un.org/feed/subscribe/en/news/all/rss.xml` | on | 200, valid RSS | Review UN terms of use before public release. |
| GDELT DOC 2.0 API | B | `https://api.gdeltproject.org/api/v2/doc/doc` (`mode=artlist&format=json`) | on | blocked by TLS interception on the dev network | Discovery references only - not a licence to republish publishers' articles, and a GDELT headline alone never establishes truth. Bounded windows (≤ 72 h), ≤ 250 records, ≥ 6 s between requests. |
| Google News RSS (India) | B | `https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en` | **off** | 200 | The feed itself says it is "made available solely for the purpose of rendering Google News results within a personal feed reader for personal, non-commercial use. Any other use of the feed is expressly prohibited." |
| ISRO | A | `https://www.isro.gov.in/` | manual | homepage 200 | No machine-readable feed verified; metadata linking / manual curation only. |
| PRS Legislative Research | A | `https://prsindia.org/` | manual | 200 | Check terms before automated extraction; interpretation, not primary authority. |
| WHO, World Bank, IMF | A | homepages | manual | WHO/World Bank 200 | Optional; enable only after testing a supported feed and its terms. |
| The Guardian Open Platform | B | `https://open-platform.theguardian.com/` | off | 200 | Eligible non-commercial development only (500 calls/day, 1 call/s); commercial or AI-derived use needs a rights review. Adapter not implemented. |
| GNews / NewsAPI | B | - | not implemented | - | Free plans restrict publication, recency and commercial use. |

## DEMO content

`apps/api/app/seed/demo.py` contains 13 hand-written explainers about well-documented past
events plus 31 static GK questions. They are labelled DEMO in the API (`is_demo`) and the UI.
Each explainer links to an official or reference page that returned HTTP 200 on 2026-10-29,
except the Olympics page (olympics.com was unreachable from the dev network; recorded in the
item metadata as `link_check: unverified`). No demo item invents a URL or claims to be today's news.

## Operational rules

* Duplicate clusters keep every supporting URL; the article page lists all sources with tier,
  publisher and publication time ("not provided by source" when absent).
* Publisher headline changes on a known URL are kept as title history and mark published
  stories "Source updated".
* Revoked source items (`fetch_status = revoked`) disappear from source lists.
* Admins can disable any source from the admin desk; disabling stops future fetches.

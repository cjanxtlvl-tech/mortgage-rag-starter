# WordPress / HFCM Chat Widget Integration

## Overview
The Veecasa mortgage chat widget is deployed in **WordPress** using **Header Footer Code Manager (HFCM)**.

This repo stores the **canonical documented copy** of the widget snippet because widget behavior depends on RAG response fields:

- `recommended_link`
- `suggested_next_action`
- `display_sources`

Keeping the documented source in-repo prevents drift between HFCM and expected RAG-powered behavior.

## Clickable Link Patch
Inside `vcBotMessage()`:

1. A URL is detected in the bot response text.
2. The raw URL is removed from visible answer text.
3. A real `<a>` button is appended.
4. Inline styles are used instead of a CSS class to avoid HFCM formatting side effects and Shadow DOM CSS issues.

## Testing Steps
1. Ask: **“Can seller pay my closing costs?”**
2. Confirm a **Learn More** button appears.
3. Confirm it links to **`/sellers-concessions`**.
4. Confirm CTA still appears.

## Cache / Publish Steps
1. Save HFCM.
2. Hard refresh.
3. Purge Cloudflare if needed.
4. Test in incognito.

## Rollback Steps
1. Restore prior HFCM snippet.
2. Remove clickable link patch if needed.

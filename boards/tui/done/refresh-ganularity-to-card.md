---
id: acfdd15a-bd6c-4dbb-8490-063dc903d3ba
title: Refresh ganularity to card
slug: refresh-ganularity-to-card
created_at: 2026-08-04T23:43:14.383246+00:00
updated_at: 2026-08-06T04:00:41.169539+00:00
priority: medium
tags: [v0.7]
created_by: phildow
---

# Description

When moving a task within a column don't refresh the whole column, just swap the cards.

When saving a card or after editing one, only refresh the card not the column.

When executing a REPL command that only affects a single card, only update that card.

# Comments

## 2026-08-06 @phildow

Have a regression to poor scrolling behavior when moving a card and especially when shift-moving.

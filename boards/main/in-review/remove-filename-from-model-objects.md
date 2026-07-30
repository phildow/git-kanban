---
id: 6082a9af-0a00-41d8-9690-a27df9c6f7d5
title: Remove filename from model objects
slug: remove-filename-from-model-objects
created_at: 2026-07-10T23:07:31.890345+00:00
updated_at: 2026-07-10T23:29:54.681600+00:00
tags: [chore]
---

# Description

The model objects are repository agnostic. They do not know about filenames, only slugs. This also means I need to remove the .md from the task path and have the repository add it as needed.

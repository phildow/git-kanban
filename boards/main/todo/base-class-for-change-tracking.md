---
id: 5be9dd68-4d6d-4c7c-8ac1-237f5bd2934b
title: Base class for change tracking
slug: base-class-for-change-tracking
created_at: 2026-08-01T09:14:36.634070+00:00
updated_at: 2026-08-04T07:18:15.319353+00:00
priority: medium
tags: [v0.8]
created_by: phildow
---

# Description

What the `GitService` conforms to, but since we're designed for any kind of repository, there may be no filesystem for git to track changes to.

For example create an in memory representation that just associates the messages with a task id and can look up every message for a task id.

This allows us to test the interface first without diving into Git details.

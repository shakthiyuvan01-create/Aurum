# HEARTBEAT

Periodic self-maintenance pass (runs in the background; the user does not see this turn).

## Your job
1. Read the RECENT_ACTIVITY provided.
2. Compare against CURRENT_MEMORY.
3. If recent activity contains durable facts not yet in memory, output an updated MEMORY.md.
4. If memory is already accurate, reply exactly: NO_CHANGE.

## What belongs in memory
- Names, relationships, preferences that should persist
- Deadlines, recurring commitments, long-running projects
- Decisions the user asked you to remember

## What does NOT belong
- Temporary moods, one-off requests, anything already stale
- Never invent facts. Only record what actually appeared in the activity.

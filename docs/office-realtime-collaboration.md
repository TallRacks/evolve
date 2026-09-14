# Office realtime collaboration boundary

Evolve Office currently uses autosave, revision conflict protection, comments, mentions, and activity. It does not advertise live cursors or presence.

A future realtime implementation should use a Yjs/CRDT document model with authenticated organization/workspace membership, server-side authorization, presence expiry, and explicit revision persistence. The transport must be authenticated WebSockets or an equivalent durable channel, with reconnect and conflict recovery. Provider content must remain outside this transport.

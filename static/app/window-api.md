Window API Contract
===================

This document lists the small, global runtime contract used by the application's no-build module split. Each extracted script registers a minimal API on `window` so `app.js` and other modules can interoperate without a bundler.

Public functions exported on window (common):

- `window.fetchJSON(url, opts)` — Promise that resolves to parsed JSON or null. Preferred implementation lives in `static/app/api.js`.
- `window.appendMessage(msg)` — Append a rendered message DOM into the messages container. Implemented by `static/app/messages.js`.
- `window.roomsApi` — namespace containing `selectRoom`, `renderRooms`, `renderContacts`, `renderMembers`, and data loaders. Implemented in `static/app/rooms.js`.
- `window.initEmojiPicker()` — Initialize emoji picker UI. Implemented in `static/app/emoji.js`.
- `window.initFileAttachments()` — Initialize file attachment UI. Implemented in `static/app/attachments.js`.
- `window.handleComposerSubmit(ev)` — Composer submit handler used by `app.js`. Implemented in `static/app/composer.js`.
- `window.initMessagesUi()` — Messages autoscroll and infinite-scroll wiring. Implemented in `static/app/messages-ui.js`.
- `window.initAuthUi(root)` — Initialize auth-related UI (logout). Implemented in `static/app/lib/auth.js`.
- `window.initComposerUi(root)` — Composer-related small UI helpers (reply-cancel, attachment clear). Implemented in `static/app/composer-ui.js`.
- `window.initSessionsUi(root)` — Session/header UI wiring (user dropdown, admin button, unread handlers). Implemented in `static/app/sessions.js`.
- `window.t(key[, lang])`, `window.setLocale(lang)`, `window.addStrings(lang, obj)` — Minimal i18n helpers. Implemented in `static/app/i18n.js`.

DOM hooks the modules expect on `window` or in the page:
- `window.messagesEl` — element with id `messages` (set by `app.js` during boot)
- `window.earliestTimestamp`, `window.latestTimestamp` — timestamps for infinite scroll tracking

Notes:
- Keep these APIs intentionally small. Add new namespaced APIs (`window.fooApi`) instead of polluting the global scope further.
- When adding or changing APIs, update both this document and `static/app/window-api.js` (JSDoc typedefs) for editor hints.
# Frontend window API contract

This short document lists the informal contract of global APIs exposed on `window` by the chat app front-end. The project intentionally exposes small functions on `window` (for no-build loading order and incremental extraction). Use this file as the canonical reference when extracting or changing behavior.

Notes
- These APIs are designed to be small, defensive, and resilient to load-order differences. Many modules will check for `typeof window.X === 'function'` before calling.
- Prefer adding the canonical implementation into a feature module (for example, `static/app/rooms.js`) and exposing the API there. Keep `static/app.js` as a thin shim delegating to these APIs where possible.

APIs (summary)

- fetchJSON(url: string, opts?: object) => Promise<any>
  - Purpose: token-aware fetch wrapper used by modules to call backend endpoints.
  - Implemented in: `static/app/api.js` (fallback present in `static/app.js`).

- appendMessage(message: Message) => HTMLElement
  - Purpose: Render a message object to a DOM node and return it. Modules append the returned node to `#messages`.
  - Implemented in: `static/app/messages.js`.

- loadRooms() => Promise<void>
- loadContacts() => Promise<void>
- loadRoomMembers(roomId: string|number) => Promise<void>
- loadRoomMessages(roomId: string|number, opts?: {before?:number, prepend?:boolean}) => Promise<void>
- loadDialogMessages(otherId: string|number, opts?: {before?:number, prepend?:boolean}) => Promise<void>
  - Purpose: Loaders for rooms, contacts and message histories. They populate `window.rooms`, `window.contacts` and render messages through `appendMessage`.
  - Implemented in: `static/app/rooms.js`.
  - Also exported as `window.roomsApi = { loadRooms, loadContacts, loadRoomMembers, loadRoomMessages, loadDialogMessages }`.

- selectRoom(roomOrId) => void
- openDialog(otherId) => void
- renderRooms() => void
- renderContacts() => void
- renderMembers(membersArr: Array<Member>) => void
  - Purpose: UI hooks for selecting rooms, opening dialogs, and rendering lists. Implementations live in the rooms module; `app.js` provides small shims that delegate.

- showModal(opts: {title?:string, body?:string, buttons?:Array<{label:string, value:any}>}) => Promise<boolean|any>
- showToast(msg: string, type?: string, timeout?: number) => void
  - Purpose: Modal and toast helpers used throughout the UI. Implemented in `static/app/ui.js` with small fallbacks in `app.js`.

- handleComposerSubmit(event: Event) => Promise<void>
  - Purpose: Composer submit handler that performs atomic message sends (and optional file upload). Implemented in `static/app/composer.js` and delegated to from `app.js`.

- initEmojiPicker() => void
  - Purpose: Initialize the inline emoji picker UI. Implemented in `static/app/emoji.js` and invoked from `app.js`.

- initFileAttachments() => void
  - Purpose: Initialize file attachment selection UI (preview/remove). Implemented in `static/app/attachments.js` and invoked from `app.js`.

- startHeartbeat(), startPresencePolling(), closePresence()
  - Purpose: Presence and heartbeat helpers. Implemented in `static/app/presence.js`.

- loadSessions() / openAdminPanel()
  - Purpose: Session and admin UI helpers. Implemented in `static/app/sessions.js` or provided by the main app.
  - Note: A fallback `openAdminPanel` implementation now exists in `static/app/admin.js` and is exposed on `window.openAdminPanel` so pages can call it regardless of header/main script ordering.

Window state (shared globals)
- window.messagesEl: HTMLElement | null — the message list container (`#messages`).
- window.earliestTimestamp: number|null — timestamp of earliest rendered message (used for infinite scroll loading older messages).
- window.latestTimestamp: number|null — timestamp of latest rendered message.
- window.autoscroll: boolean — whether the UI should auto-scroll to bottom when new messages arrive.
- window.currentRoom: Room|null — the currently selected room object.
- window.isDialog: boolean — whether `currentRoom` is a dialog (1:1).
- window.rooms: Array<Room> — loaded rooms list.
- window.contacts: Array<Contact> — loaded contact list.

Types (informal)
- Room
  - id: number|string
  - name?: string
  - other_name?: string
  - is_dialog?: boolean
  - members?: Array<number>

- Message
  - id: number|string
  - room_id: number|string
  - sender_id: number|string
  - text?: string
  - created_at: number
  - is_me?: boolean

- Member
  - id: number|string
  - name: string
  - online: boolean

Guidelines
- When extracting a function from `app.js` into a module, add its implementation file under `static/app/` and expose the function on `window` (or under `window.<feature>Api`) so other extracted modules can access it without coupling to load order.
- Prefer to expose a small namespace (for example `window.roomsApi`) when multiple related functions belong together.
- Keep `app.js` shims minimal and defensive: check `typeof window.X === 'function'` before calling.

Example (recommended pattern)

1. Implement in `static/app/rooms.js`:

   - export canonical functions like `loadRooms`, `selectRoom`, etc., then assign `window.roomsApi = { loadRooms, selectRoom, ... }` and/or assign individual functions on `window`.

2. In `static/app.js` (bootstrap/glue):

   - call `if (window.roomsApi && typeof window.roomsApi.loadRooms === 'function') await window.roomsApi.loadRooms();` rather than directly importing or inlining the implementation.

This file is the single-file contract/reference for current global APIs. Keep it updated as you extract more functionality.
